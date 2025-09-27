# sniff_pixeldrain_ws.py
"""
WebSocket sniffer for Pixeldrain file stats.
Uses Chrome DevTools Protocol via pychrome to capture frames
and extract useful metadata such as file size and transfer limits.
"""

import base64
import json
import re
import sys
import time
from threading import Event
from typing import Any, Dict, Optional

import json5
import pychrome
from bs4 import BeautifulSoup

# --- Constants ---
TARGET_WS = "wss://pixeldrain.com/api/file_stats"
CHROME_URL = "http://127.0.0.1:9222"
PIXELDRAIN_URL = "https://pixeldrain.com/u/xxxxxx"

# --- Globals (state tracking) ---
ws_map: Dict[str, str] = {}
transfer_limit_used: Optional[int] = None
transfer_limit: Optional[int] = None
stop_event = Event()


# --- Utility Functions ---
def try_parse_payload(payload: Any) -> Any:
    """Try to decode payload data to JSON if possible, otherwise return raw."""
    if not isinstance(payload, str):
        return payload

    # Try plain JSON
    try:
        return json.loads(payload)
    except Exception:
        pass

    # Try base64 → JSON
    try:
        decoded = base64.b64decode(payload)
        return json.loads(decoded.decode("utf-8", errors="ignore"))
    except Exception:
        return payload


def extract_viewer_data(html: str) -> Optional[Dict[str, Any]]:
    """Extract and parse window.viewer_data object from page HTML."""
    soup = BeautifulSoup(html, "html.parser")
    script = soup.find("script", string=re.compile(r"window\.viewer_data"))
    if not script:
        return None

    match = re.search(r"window\.viewer_data\s*=\s*({.*?});", script.string, re.S)
    if not match:
        return None

    try:
        return json5.loads(match.group(1))
    except Exception as e:
        print(f"[Error] Failed to parse viewer_data: {e}")
        return None


# --- WebSocket Event Handlers ---
def on_ws_created(requestId=None, url=None, **kwargs):
    if url == TARGET_WS:
        ws_map[requestId] = url
        print(f"[+] Tracking target websocket: {url}")


def on_ws_closed(requestId=None, **kwargs):
    if requestId in ws_map:
        print(f"[-] Target websocket closed: id={requestId}")
        del ws_map[requestId]


def on_ws_frame_received(requestId=None, response=None, **kwargs):
    global transfer_limit_used, transfer_limit
    if requestId not in ws_map:
        return

    payload = response.get("payloadData")
    opcode = response.get("opcode")
    parsed = None

    if opcode == 1:  # text
        parsed = try_parse_payload(payload)
    elif opcode == 2:  # binary
        try:
            raw = base64.b64decode(payload)
            parsed = json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception:
            parsed = payload

    print("\n--- [WS FRAME RECEIVED] ---")
    if isinstance(parsed, dict):
        print(json.dumps(parsed, indent=2))
        if parsed.get("type") == "limits":
            print(">>> Detected limits message.")
        limits = parsed.get("limits", {})
        transfer_limit_used = limits.get("transfer_limit_used", transfer_limit_used)
        transfer_limit = limits.get("transfer_limit", transfer_limit)
        if transfer_limit is not None:
            stop_event.set()
    else:
        print(parsed)
    print("--------------------------\n")


def on_ws_frame_sent(requestId=None, response=None, **kwargs):
    if requestId in ws_map:
        print(f"[WS Sent] payload: {response.get('payloadData')}")


# --- Main Workflow ---
def run_sniffer() -> None:
    global transfer_limit_used, transfer_limit

    browser = pychrome.Browser(url=CHROME_URL)
    tab = browser.new_tab()

    # Bind events
    tab.Network.webSocketCreated = on_ws_created
    tab.Network.webSocketClosed = on_ws_closed
    tab.Network.webSocketFrameReceived = on_ws_frame_received
    tab.Network.webSocketFrameSent = on_ws_frame_sent

    file_size: Optional[int] = None

    try:
        tab.start()
        tab.Network.enable()
        tab.Page.enable()

        print(f"Navigating to {PIXELDRAIN_URL}...")
        tab.Page.navigate(url=PIXELDRAIN_URL)
        time.sleep(5)  # allow page load

        # Extract viewer_data
        html = tab.Runtime.evaluate(
            expression="document.documentElement.outerHTML"
        )["result"]["value"]

        data = extract_viewer_data(html)
        if data and "api_response" in data:
            file_size = data["api_response"].get("size")
            print(f"Detected file size: {file_size} bytes")
        else:
            print("[!] Could not extract viewer_data.")

        print("Waiting for websocket frames (Ctrl+C to stop)...")
        while not stop_event.is_set():
            time.sleep(0.5)
            if transfer_limit_used is not None:
                print(f"Transfer limit used so far: {transfer_limit_used} bytes")
                stop_event.set()

    except KeyboardInterrupt:
        print("Interrupted by user.")
    finally:
        try:
            tab.stop()
            browser.close_tab(tab)

            print(f"\n--- Final Report ---")
            print(f"File size: {file_size} bytes")
            print(f"Transfer limit used: {transfer_limit_used} bytes")
            print(f"Total transfer limit: {transfer_limit} bytes")

            if (
                file_size is not None
                and transfer_limit is not None
                and transfer_limit_used is not None
            ):
                remaining = transfer_limit - transfer_limit_used
                if remaining > file_size:
                    print("[OK] Download can complete within the transfer limit.")
                else:
                    print("[WARN] Download may NOT complete within the transfer limit.")
        except Exception as e:
            print(f"[Error] Cleanup failed: {e}")
        print("Stopped.")


if __name__ == "__main__":
    run_sniffer()
