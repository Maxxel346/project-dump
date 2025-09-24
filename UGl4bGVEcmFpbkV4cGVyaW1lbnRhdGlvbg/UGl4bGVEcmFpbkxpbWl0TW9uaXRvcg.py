# sniff_pixeldrain_ws.py
import pychrome
import json
import base64
import time
import sys
from threading import Event
transfer_limit_used = None

# Target websocket URL to filter for
TARGET_WS = "wss://pixeldrain.com/api/file_stats"

# map from requestId -> url
ws_map = {}

stop_event = Event()

def on_ws_created(requestId=None, url=None, **kwargs):
    # Called when a websocket is created by the page
    print(f"[WS Created] id={requestId} url={url}")
    if url == TARGET_WS:
        ws_map[requestId] = url
        print("[+] Tracking target websocket:", url)

def on_ws_closed(requestId=None, **kwargs):
    if requestId in ws_map:
        print(f"[-] Target websocket closed: id={requestId}")
        del ws_map[requestId]

def try_parse_payload(payload):
    """Try to decode payload data to JSON if possible, otherwise return raw."""
    # payload is usually a str for text frames. For binary frames some CDP versions
    # return base64; we attempt to detect that.
    if isinstance(payload, str):
        # Try JSON
        try:
            return json.loads(payload)
        except Exception:
            # maybe base64-encoded binary JSON
            try:
                decoded = base64.b64decode(payload)
                return json.loads(decoded.decode("utf-8", errors="ignore"))
            except Exception:
                return payload
    else:
        return payload

def on_ws_frame_received(requestId=None, timestamp=None, response=None, **kwargs):
    global transfer_limit_used
    # response contains: opcode, mask, payloadData
    if requestId not in ws_map:
        return  # ignore other websockets

    payload = response.get("payloadData")
    opcode = response.get("opcode")  # 1=text, 2=binary
    parsed = None
    if opcode == 1:
        parsed = try_parse_payload(payload)
    elif opcode == 2:
        # binary: payload may be base64. attempt to decode & parse JSON
        try:
            raw = base64.b64decode(payload)
            parsed = json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception:
            parsed = payload

    # Print nicely
    print("\n--- [WS FRAME RECEIVED] ---")
    if isinstance(parsed, dict):
        # pretty print JSON; and highlight if it's type=limits
        print(json.dumps(parsed, indent=2))
        if parsed.get("type") == "limits":
            print(">>> Detected limits message.")
        limits = parsed.get("limits", {})
        if "transfer_limit_used" in limits:
            transfer_limit_used = limits["transfer_limit_used"]
    else:
        print(parsed)
    print("--------------------------\n")

def on_ws_frame_sent(requestId=None, response=None, **kwargs):
    if requestId not in ws_map:
        return
    payload = response.get("payloadData")
    print("[WS Sent] payload:", payload)

def main():
    # connect to running Chrome
    browser = pychrome.Browser(url="http://127.0.0.1:9222")
    tab = browser.new_tab()

    # bind handlers
    tab.Network.webSocketCreated = on_ws_created
    tab.Network.webSocketClosed = on_ws_closed
    tab.Network.webSocketFrameReceived = on_ws_frame_received
    tab.Network.webSocketFrameSent = on_ws_frame_sent

    try:
        tab.start()
        tab.Network.enable()
        tab.Page.enable()

        # navigate to site (if you want the page to open here)
        print("Navigating to pixeldrain.com in the controlled tab...")
        tab.Page.navigate(url="https://pixeldrain.com/u/xxxxx")
        # keep running until Ctrl+C
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
        except Exception:
            pass
        print("Stopped.")

if __name__ == "__main__":
    main()
