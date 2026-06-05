"""Capture reproducible screenshots for README and presentation assets."""

from __future__ import annotations

import base64
import json
import shutil
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

import websocket


ROOT = Path(__file__).resolve().parents[1]
ASSET_DIR = ROOT / "docs" / "assets"
CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")
REMOTE_PORT = 9222
URL = "http://localhost:8501"


class CdpClient:
    def __init__(self, ws_url: str) -> None:
        self.ws = websocket.create_connection(ws_url, timeout=10)
        self.next_id = 1

    def call(self, method: str, params: dict | None = None) -> dict:
        msg_id = self.next_id
        self.next_id += 1
        self.ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get("id") == msg_id:
                if "error" in msg:
                    raise RuntimeError(f"CDP error for {method}: {msg['error']}")
                return msg.get("result", {})

    def close(self) -> None:
        self.ws.close()


def _request_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _open_tab(url: str) -> dict:
    request = urllib.request.Request(
        f"http://127.0.0.1:{REMOTE_PORT}/json/new?{url}",
        method="PUT",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_chrome() -> None:
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            _request_json(f"http://127.0.0.1:{REMOTE_PORT}/json/version")
            return
        except Exception:
            time.sleep(0.25)
    raise TimeoutError("Chrome DevTools endpoint did not start.")


def _wait_for_text(cdp: CdpClient, text: str, timeout: int = 60) -> None:
    deadline = time.time() + timeout
    expression = f"document.body && document.body.innerText.includes({json.dumps(text)})"
    while time.time() < deadline:
        result = cdp.call("Runtime.evaluate", {"expression": expression, "returnByValue": True})
        if result.get("result", {}).get("value"):
            return
        time.sleep(0.5)
    raise TimeoutError(f"Timed out waiting for text: {text}")


def _capture(cdp: CdpClient, path: Path) -> None:
    metrics = cdp.call("Page.getLayoutMetrics")
    content = metrics["contentSize"]
    width = max(1440, int(content["width"]))
    height = max(1350, int(content["height"]))
    cdp.call(
        "Emulation.setDeviceMetricsOverride",
        {
            "width": width,
            "height": height,
            "deviceScaleFactor": 1,
            "mobile": False,
        },
    )
    image = cdp.call(
        "Page.captureScreenshot",
        {
            "format": "png",
            "captureBeyondViewport": True,
            "fromSurface": True,
        },
    )
    path.write_bytes(base64.b64decode(image["data"]))


def capture() -> None:
    if not CHROME.exists():
        raise FileNotFoundError(f"Chrome not found: {CHROME}")

    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    chrome_profile_parent = ROOT / ".tmp"
    chrome_profile_parent.mkdir(exist_ok=True)
    profile = tempfile.mkdtemp(prefix="chrome-cdp-", dir=chrome_profile_parent)

    chrome = subprocess.Popen(
        [
            str(CHROME),
            "--headless=new",
            f"--remote-debugging-port={REMOTE_PORT}",
            f"--user-data-dir={profile}",
            "--window-size=1440,1350",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            "--remote-allow-origins=*",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    cdp: CdpClient | None = None
    try:
        _wait_for_chrome()
        tab = _open_tab(URL)
        cdp = CdpClient(tab["webSocketDebuggerUrl"])
        cdp.call("Page.enable")
        cdp.call("Runtime.enable")
        cdp.call("Page.navigate", {"url": URL})
        _wait_for_text(cdp, "跨境电商资金流审计 Agent", timeout=30)
        time.sleep(1.5)
        _capture(cdp, ASSET_DIR / "streamlit-demo-home.png")

        click_script = """
        (() => {
          const buttons = Array.from(document.querySelectorAll('button'));
          const button = buttons.find((el) => el.innerText.includes('使用内置示例生成底稿'));
          if (!button) return false;
          button.click();
          return true;
        })()
        """
        result = cdp.call("Runtime.evaluate", {"expression": click_script, "returnByValue": True})
        if not result.get("result", {}).get("value"):
            raise RuntimeError("Demo button was not found.")
        _wait_for_text(cdp, "示例底稿已生成", timeout=60)
        time.sleep(1.0)
        _capture(cdp, ASSET_DIR / "streamlit-demo-result.png")
    finally:
        if cdp:
            cdp.close()
        chrome.terminate()
        try:
            chrome.wait(timeout=5)
        except subprocess.TimeoutExpired:
            chrome.kill()
        shutil.rmtree(profile, ignore_errors=True)


if __name__ == "__main__":
    capture()
    print(f"Screenshots written to {ASSET_DIR}")
