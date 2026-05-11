# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, request

from .config import Settings, get_settings
from .pipeline import AuditPipelineResult, run_audit_pipeline
from .rag import AuditKnowledgeBase, RetrievedChunk, format_chunk_citation


@dataclass
class FeishuMessageEvent:
    chat_id: str
    chat_type: str
    message_id: str
    message_type: str
    text: str


GREETING_TOKENS = {
    "hi",
    "hello",
    "hey",
    "嗨",
    "哈喽",
    "你好",
    "你好啊",
    "你好呀",
    "您好",
    "在吗",
    "在不",
    "在嘛",
    "早上好",
    "上午好",
    "中午好",
    "下午好",
    "晚上好",
}


def append_runtime_log(settings: Settings, level: str, message: str) -> None:
    log_dir = settings.project_root / "output" / "runtime_logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "feishu_runtime.log"
    timestamp = datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    with log_file.open("a", encoding="utf-8") as handle:
        handle.write(f"{timestamp} [{level}] {message}\n")


def open_without_proxy(req: request.Request, timeout: int) -> Any:
    opener = request.build_opener(request.ProxyHandler({}))
    return opener.open(req, timeout=timeout)


class FeishuBotClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self._app_access_token = ""
        self._expire_at = 0.0
        self._lock = threading.Lock()

    def send_text(self, chat_id: str, text: str) -> dict[str, Any]:
        token = self._get_app_access_token()
        payload = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}, ensure_ascii=False),
            "uuid": str(uuid.uuid4()),
        }
        return self._post_json(
            url="https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            payload=payload,
            headers={"Authorization": f"Bearer {token}"},
        )

    def _get_app_access_token(self) -> str:
        with self._lock:
            if self._app_access_token and time.time() < self._expire_at:
                return self._app_access_token
            response = self._post_json(
                url="https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
                payload={
                    "app_id": self.settings.feishu_app_id,
                    "app_secret": self.settings.feishu_app_secret,
                },
                headers={},
            )
            token = str(response.get("app_access_token") or response.get("tenant_access_token") or "")
            if not token:
                raise RuntimeError(f"Failed to get Feishu app_access_token: {response}")
            expire = int(response.get("expire", 7200))
            self._app_access_token = token
            self._expire_at = time.time() + max(expire - 60, 60)
            return token

    def _post_json(self, url: str, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = request.Request(
            url=url,
            data=body,
            headers={"Content-Type": "application/json; charset=utf-8", **headers},
            method="POST",
        )
        try:
            with open_without_proxy(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            append_runtime_log(self.settings, "ERROR", f"Feishu API HTTP {exc.code}: {raw}")
            raise RuntimeError(f"Feishu API HTTP {exc.code}: {raw}") from exc
        except Exception as exc:
            append_runtime_log(self.settings, "ERROR", f"Feishu API request failed: {exc}")
            raise


class FeishuWebhookApp:
    def __init__(self, settings: Settings | None = None, bot_client: FeishuBotClient | None = None):
        self.settings = settings or get_settings()
        self.bot_client = bot_client or FeishuBotClient(self.settings)
        self._seen_message_ids: set[str] = set()
        self._seen_lock = threading.Lock()

    def handle_payload(self, payload: dict[str, Any]) -> tuple[int, dict[str, Any]]:
        if "encrypt" in payload:
            append_runtime_log(
                self.settings,
                "WARN",
                "Received encrypted Feishu payload. Disable Event Subscription encryption for this project.",
            )
            return 400, {"code": 400, "msg": "encrypted payload unsupported"}

        if payload.get("type") == "url_verification":
            if not self._token_ok(payload):
                append_runtime_log(self.settings, "WARN", "Feishu url_verification failed: invalid verification token.")
                return 403, {"code": 403, "msg": "invalid verification token"}
            append_runtime_log(self.settings, "INFO", "Feishu url_verification succeeded.")
            return 200, {"challenge": payload.get("challenge", "")}

        event_type = str(payload.get("header", {}).get("event_type", ""))
        if event_type != "im.message.receive_v1":
            if event_type:
                append_runtime_log(self.settings, "INFO", f"Ignored Feishu event type: {event_type}")
            return 200, {"code": 0, "msg": "ignored"}

        if not self._token_ok(payload):
            append_runtime_log(self.settings, "WARN", "Feishu event rejected: invalid verification token.")
            return 403, {"code": 403, "msg": "invalid verification token"}

        event = self._parse_message_event(payload)
        if not event or not event.text:
            append_runtime_log(self.settings, "INFO", "Ignored Feishu message event without usable text payload.")
            return 200, {"code": 0, "msg": "ignored"}

        if self._is_duplicate(event.message_id):
            append_runtime_log(self.settings, "INFO", f"Ignored duplicate Feishu message: {event.message_id}")
            return 200, {"code": 0, "msg": "duplicate"}

        append_runtime_log(
            self.settings,
            "INFO",
            f"Accepted Feishu message {event.message_id} from chat_type={event.chat_type or 'unknown'}.",
        )
        thread = threading.Thread(target=self._process_message_event, args=(event,), daemon=True)
        thread.start()
        return 200, {"code": 0, "msg": "ok"}

    def _process_message_event(self, event: FeishuMessageEvent) -> None:
        try:
            reply = self._dispatch_text(event.text)
        except Exception as exc:
            append_runtime_log(self.settings, "ERROR", f"Failed to build reply for {event.message_id}: {exc}")
            reply = f"处理消息时出错: {exc}"
        try:
            self.bot_client.send_text(event.chat_id, trim_for_feishu(reply))
            append_runtime_log(self.settings, "INFO", f"Sent Feishu reply for {event.message_id}.")
        except Exception as exc:
            append_runtime_log(self.settings, "ERROR", f"Failed to send Feishu reply for {event.message_id}: {exc}")

    def _dispatch_text(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return "收到空消息。发送 #help 查看用法。"
        if is_greeting_text(normalized):
            return build_greeting_text(self.settings)
        if normalized.lower() in {"#help", "/help", "help"}:
            return build_help_text(self.settings)
        if normalized.lower() in {"#doctor", "/doctor"}:
            return build_doctor_text(self.settings)
        if normalized.startswith("#search ") or normalized.startswith("/search "):
            query = normalized.split(" ", 1)[1].strip()
            return build_search_reply(self.settings, query)

        mode = self.settings.feishu_default_mode if self.settings.feishu_default_mode in {"mock", "autogen"} else "autogen"
        result = run_audit_pipeline(mode=mode, case_description=normalized)
        return build_pipeline_reply(result)

    def _token_ok(self, payload: dict[str, Any]) -> bool:
        expected = self.settings.feishu_verification_token.strip()
        if not expected:
            return True
        actual = str(payload.get("token") or payload.get("header", {}).get("token") or "")
        return actual == expected

    def _parse_message_event(self, payload: dict[str, Any]) -> FeishuMessageEvent | None:
        event = payload.get("event") or {}
        message = event.get("message") or {}
        sender = event.get("sender") or {}
        if str(sender.get("sender_type", "")).lower() == "app":
            return None
        if str(message.get("message_type", "")) != "text":
            return None
        chat_id = str(message.get("chat_id") or "")
        message_id = str(message.get("message_id") or "")
        chat_type = str(message.get("chat_type") or "")
        content = message.get("content") or ""
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
        except Exception:
            parsed = {}
        text = str(parsed.get("text") or "").strip()
        if not chat_id or not message_id:
            return None
        return FeishuMessageEvent(
            chat_id=chat_id,
            chat_type=chat_type,
            message_id=message_id,
            message_type="text",
            text=text,
        )

    def _is_duplicate(self, message_id: str) -> bool:
        with self._seen_lock:
            if message_id in self._seen_message_ids:
                return True
            self._seen_message_ids.add(message_id)
            if len(self._seen_message_ids) > 1000:
                self._seen_message_ids = set(list(self._seen_message_ids)[-500:])
            return False


def create_feishu_handler(app: FeishuWebhookApp):
    class FeishuHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            if self.path != app.settings.feishu_path:
                self._send_json(404, {"code": 404, "msg": "not found"})
                return
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            try:
                payload = json.loads(raw.decode("utf-8"))
            except Exception:
                self._send_json(400, {"code": 400, "msg": "invalid json"})
                return
            status, body = app.handle_payload(payload)
            self._send_json(status, body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == app.settings.feishu_path:
                self._send_json(200, {"code": 0, "msg": "feishu webhook is running"})
            else:
                self._send_json(404, {"code": 404, "msg": "not found"})

        def log_message(self, format: str, *args: Any) -> None:
            return

        def _send_json(self, status: int, body: dict[str, Any]) -> None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

    return FeishuHandler


def serve_feishu_webhook(settings: Settings | None = None) -> None:
    app = FeishuWebhookApp(settings=settings)
    host = app.settings.feishu_host
    port = app.settings.feishu_port
    server = ThreadingHTTPServer((host, port), create_feishu_handler(app))
    print(f"Feishu webhook listening on http://{host}:{port}{app.settings.feishu_path}")
    print("Send #help in Feishu after configuring event subscription.")
    append_runtime_log(app.settings, "INFO", f"Feishu webhook server started on http://{host}:{port}{app.settings.feishu_path}")
    server.serve_forever()


def build_help_text(settings: Settings) -> str:
    return (
        "审计 Agent 已接入飞书。\n"
        "可用命令:\n"
        "1. 直接发送审计问题：例如“分析固定资产费用化风险”。\n"
        "2. #search 会计估计 重大错报风险 审计证据\n"
        "3. #doctor\n"
        f"默认运行模式: {settings.feishu_default_mode}\n"
        f"样例凭证: {settings.sample_data_path.name}\n"
        f"本地知识库: {settings.local_knowledge_dir.name}"
    )


def build_greeting_text(settings: Settings) -> str:
    return (
        "你好，我是审计 Agent。\n"
        "你可以这样和我说：\n"
        "1. 直接发审计问题，例如“分析固定资产费用化风险”。\n"
        "2. 发 `#search 关键词` 检索审计依据。\n"
        "3. 发 `#help` 查看用法，发 `#doctor` 查看当前配置。\n"
        f"当前默认模式: {settings.feishu_default_mode}"
    )


def build_doctor_text(settings: Settings) -> str:
    statuses = [
        f"DeepSeek Key: {'已配置' if settings.deepseek_api_key else '未配置'}",
        f"模型: {settings.llm_model}",
        f"飞书 App ID: {'已配置' if settings.feishu_app_id else '未配置'}",
        f"飞书校验 Token: {'已配置' if settings.feishu_verification_token else '未配置'}",
        f"本地知识库目录: {settings.local_knowledge_dir}",
    ]
    return "\n".join(statuses)


def build_search_reply(settings: Settings, query: str, top_k: int = 3) -> str:
    kb = AuditKnowledgeBase([settings.sample_knowledge_dir, settings.local_knowledge_dir], settings.chroma_dir)
    chunks = kb.search(query, top_k=top_k)
    if not chunks:
        return f"未检索到与“{query}”相关的依据。"
    lines = [f"检索词: {query}", f"命中 {len(chunks)} 条依据:"]
    for idx, chunk in enumerate(chunks, start=1):
        excerpt = chunk.text.replace("\n", " ").strip()
        if len(excerpt) > 160:
            excerpt = excerpt[:160] + "..."
        lines.append(f"{idx}. {format_chunk_citation(chunk)}")
        lines.append(f"   {excerpt}")
    return "\n".join(lines)


def build_pipeline_reply(result: AuditPipelineResult) -> str:
    partner_turn = next((turn.content for turn in result.turns if turn.speaker == "Audit_Partner"), "")
    summary = partner_turn or "已完成审计分析。"
    if len(summary) > 900:
        summary = summary[:900] + "..."
    finding_lines = []
    for finding in result.findings[:3]:
        finding_lines.append(f"- [{finding.risk_level}] {finding.issue} ({finding.voucher_id})")
    finding_text = "\n".join(finding_lines) if finding_lines else "- 未识别到高风险发现"
    rag_text = ""
    if result.rag_chunks:
        rag_text = "\n".join(f"- {format_chunk_citation(chunk)}" for chunk in result.rag_chunks[:2])
    return (
        f"审计分析已完成（{result.mode}）。\n"
        f"样本凭证: {len(result.vouchers)}\n"
        f"异常发现: {len(result.findings)}\n"
        f"关键发现:\n{finding_text}\n"
        f"复核意见摘要:\n{summary}\n"
        + (f"参考依据:\n{rag_text}\n" if rag_text else "")
        + f"本地底稿: {result.report_path}"
    )


def trim_for_feishu(text: str, limit: int = 3500) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def is_greeting_text(text: str) -> bool:
    compact = "".join(
        ch.lower()
        for ch in text
        if ch.isascii() and ch.isalnum() or "\u4e00" <= ch <= "\u9fff"
    )
    return compact in GREETING_TOKENS
