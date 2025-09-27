# sniff_pixeldrain_ws.py
"""
Pixeldrain WebSocket Sniffer

This script uses Chrome DevTools Protocol (via pychrome) to:
- Capture WebSocket frames from Pixeldrain's API
- Extract file size and transfer limits
- Report whether a file can be downloaded within the current transfer limit
"""

import base64
import json
import re
import time
import logging
from threading import Event
from typing import Any, Dict, Optional

import json5
import pychrome
from bs4 import BeautifulSoup

from extensionVeepn import mainConnection

# --- Logging Configuration ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

# --- Constants ---
TARGET_WS = "wss://pixeldrain.com/api/file_stats"
CHROME_URL = "http://127.0.0.1:9222"
PIXELDRAIN_URL = "https://pixeldrain.com/u/xxxx"

# --- State Variables ---
ws_map: Dict[str, str] = {}
transfer_limit_used: Optional[int] = None
transfer_limit: Optional[int] = None
stop_event = Event()


# --- Utility Functions ---
def try_parse_payload(payload: Any) -> Any:
    """Attempt to parse WebSocket payload as JSON, fallback to raw."""
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
    """Extract and parse `window.viewer_data` from Pixeldrain page HTML."""
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
        logging.error("Failed to parse viewer_data: %s", e)
        return None


# --- WebSocket Event Handlers ---
def on_ws_created(requestId=None, url=None, **_):
    if url == TARGET_WS:
        ws_map[requestId] = url
        logging.info("[+] Tracking WebSocket: %s", url)


def on_ws_closed(requestId=None, **_):
    if requestId in ws_map:
        logging.info("[-] WebSocket closed (id=%s)", requestId)
        del ws_map[requestId]


def on_ws_frame_received(requestId=None, response=None, **_):
    """Process incoming WebSocket frames and extract transfer limits."""
    global transfer_limit_used, transfer_limit
    if requestId not in ws_map:
        return

    payload = response.get("payloadData")
    opcode = response.get("opcode")
    parsed = None

    if opcode == 1:  # text frame
        parsed = try_parse_payload(payload)
    elif opcode == 2:  # binary frame
        try:
            raw = base64.b64decode(payload)
            parsed = json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception:
            parsed = payload

    logging.info("--- [WS FRAME RECEIVED] ---")
    if isinstance(parsed, dict):
        logging.debug("Full JSON frame: %s", json.dumps(parsed, indent=2))
        if parsed.get("type") == "limits":
            logging.info(">>> Detected 'limits' message.")

        limits = parsed.get("limits", {})
        transfer_limit_used = limits.get("transfer_limit_used", transfer_limit_used)
        transfer_limit = limits.get("transfer_limit", transfer_limit)

        if transfer_limit is not None:
            stop_event.set()
    else:
        logging.info("%s", parsed)
    logging.info("---------------------------")


def on_ws_frame_sent(requestId=None, response=None, **_):
    if requestId in ws_map:
        logging.debug("[WS Sent] Payload: %s", response.get("payloadData"))


# --- Main Workflow ---
def run_sniffer(browser: Optional[pychrome.Browser] = None) -> bool:
    """
    Run Pixeldrain WebSocket sniffer.
    
    Args:
        browser (pychrome.Browser): Active pychrome browser instance.

    Returns:
        bool: True if download is possible within transfer limit, False otherwise.
    """
    global transfer_limit_used, transfer_limit
    if browser is None:
        browser = pychrome.Browser(url=CHROME_URL)

    tab = browser.new_tab()

    # Bind WebSocket event handlers
    tab.Network.webSocketCreated = on_ws_created
    tab.Network.webSocketClosed = on_ws_closed
    tab.Network.webSocketFrameReceived = on_ws_frame_received
    tab.Network.webSocketFrameSent = on_ws_frame_sent

    file_size: Optional[int] = None

    try:
        tab.start()
        tab.Network.enable()
        tab.Page.enable()

        logging.info("Navigating to %s...", PIXELDRAIN_URL)
        tab.Page.navigate(url=PIXELDRAIN_URL)
        time.sleep(5)  # Allow page to load

        # Extract file metadata
        html = tab.Runtime.evaluate(expression="document.documentElement.outerHTML")["result"]["value"]
        data = extract_viewer_data(html)

        if data and "api_response" in data:
            file_size = data["api_response"].get("size")
            logging.info("Detected file size: %s bytes", file_size)
        else:
            logging.warning("Failed to extract viewer_data from page.")

        logging.info("Waiting for WebSocket frames...")
        while not stop_event.is_set():
            time.sleep(0.5)
            if transfer_limit_used is not None:
                logging.info("Transfer limit used so far: %s bytes", transfer_limit_used)
                stop_event.set()

    except KeyboardInterrupt:
        logging.warning("Interrupted by user.")
    finally:
        try:
            tab.Runtime.evaluate(expression="1+1;")  # Dummy eval to keep the tab responsive
            logging.info("--- Final Report ---")
            logging.info("File size: %s bytes", file_size)
            logging.info("Transfer limit used: %s bytes", transfer_limit_used)
            logging.info("Total transfer limit: %s bytes", transfer_limit)
            if all(v is not None for v in (file_size, transfer_limit, transfer_limit_used)):
                remaining = transfer_limit - transfer_limit_used
                if remaining > file_size:
                    logging.info("[OK] Download can complete within transfer limit.")
                    tab.Runtime.evaluate(expression="""
                        (() => {
                        const btn = Array.from(document.querySelectorAll("button.button_highlight"))
                            .find(b => b.querySelector("i.icon") && b.querySelector("span")?.textContent.trim());
                        if (btn) {
                            btn.click();
                            return "clicked";
                        }
                        return "not found";
                        })()
                    """)
                    logging.info("Clicked download button.")
                    return True
                else:
                    logging.warning("[WARN] Insufficient transfer limit. Consider VPN reconnect.")
                    return False
            time.sleep(1)
            tab.stop()
            browser.close_tab(tab)
        except Exception as e:
            logging.error("Error during cleanup: %s", e)

        logging.info("Stopped.")
        return False


# --- Entry Point ---
if __name__ == "__main__":
    browser = pychrome.Browser(url=CHROME_URL)
    while True:
        if run_sniffer(browser=browser):
            break
        mainConnection()

