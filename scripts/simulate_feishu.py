# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import time

from audit_multi_agent_rag.audit_rag.feishu import FeishuBotClient, FeishuWebhookApp


class DummyFeishuBotClient(FeishuBotClient):
    def __init__(self):
        pass

    def send_text(self, chat_id: str, text: str) -> dict:
        print("SEND_TO_CHAT:", chat_id)
        print(text)
        return {"code": 0, "msg": "ok"}


def main() -> None:
    os.environ["FEISHU_DEFAULT_MODE"] = "mock"
    app = FeishuWebhookApp(bot_client=DummyFeishuBotClient())

    verify_payload = {
        "type": "url_verification",
        "token": app.settings.feishu_verification_token,
        "challenge": "test-challenge",
    }
    print("VERIFY:", app.handle_payload(verify_payload))

    search_payload = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
            "token": app.settings.feishu_verification_token,
        },
        "event": {
            "sender": {"sender_type": "user"},
            "message": {
                "chat_id": "oc_test_chat",
                "chat_type": "p2p",
                "message_id": "msg-search-1",
                "message_type": "text",
                "content": json.dumps({"text": "#search 会计估计 重大错报风险 审计证据"}, ensure_ascii=False),
            },
        },
    }
    print("SEARCH_EVENT:", app.handle_payload(search_payload))

    run_payload = {
        "schema": "2.0",
        "header": {
            "event_type": "im.message.receive_v1",
            "token": app.settings.feishu_verification_token,
        },
        "event": {
            "sender": {"sender_type": "user"},
            "message": {
                "chat_id": "oc_test_chat",
                "chat_type": "p2p",
                "message_id": "msg-run-1",
                "message_type": "text",
                "content": json.dumps({"text": "分析固定资产费用化风险，并形成初步审计意见。"}, ensure_ascii=False),
            },
        },
    }
    print("RUN_EVENT:", app.handle_payload(run_payload))
    time.sleep(6)


if __name__ == "__main__":
    main()
