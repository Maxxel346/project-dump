import time
import random
import logging
import pychrome
import pyautogui
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def init_browser(debug_url: str = "http://127.0.0.1:9222", wait_time: int = 5) -> pychrome.Browser:
    logging.info("Connecting to Chrome at %s", debug_url)
    browser = pychrome.Browser(url=debug_url)
    time.sleep(wait_time)
    return browser


def open_extension_popup():
    logging.info("Opening extension popup with hotkey...")
    pyautogui.hotkey("ctrl", "shift", "h")


def find_extension_tab(browser: pychrome.Browser, extension_id: str) -> pychrome.Tab:
    logging.info("Scanning tabs for extension id: %s", extension_id)

    for i, tab in enumerate(browser.list_tab()):
        try:
            tab.start()
            tab.Page.enable()
            tab.Runtime.enable()

            result = tab.Runtime.evaluate(
                expression="document.head.innerHTML",
                returnByValue=True
            )
            html = result["result"]["value"]

            if extension_id in html:
                logging.info("Found extension tab at index %d, id=%s, url=%s", i, tab.id, tab.url)
                return tab

        except Exception as e:
            logging.error("Error scanning tab %d: %s", i, e)
            tab.stop()

    logging.warning("Extension tab not found.")
    return None


def get_connection_status(tab: pychrome.Tab) -> str:
    """
    Return 'connected' or 'disconnected' based on the button class.
    """
    result = tab.call_method(
        "Runtime.evaluate",
        expression="""
        (function(){
            var btn = document.querySelector('.connect-button');
            if (!btn) return "unknown";
            if (btn.classList.contains('connect-button--connected')) return "connected";
            if (btn.classList.contains('connect-button--disconnected')) return "disconnected";
            return "unknown";
        })();
        """
    )
    return result["result"]["value"]


def wait_until_connected(tab: pychrome.Tab, timeout: int = 20, interval: float = 1.0) -> bool:
    """
    Wait until the extension shows 'connected' state.
    """
    logging.info("Waiting for VPN to connect...")
    start = time.time()

    while time.time() - start < timeout:
        status = get_connection_status(tab)
        logging.info("Current status: %s", status)
        if status == "connected":
            logging.info("VPN is now connected ✅")
            return True
        time.sleep(interval)

    logging.warning("Timeout: VPN did not connect within %d seconds", timeout)
    return False


def connect(tab: pychrome.Tab):
    """
    Connect if currently disconnected.
    """
    status = get_connection_status(tab)
    logging.info("Initial status: %s", status)

    if status == "disconnected":
        logging.info("Clicking connect...")
        tab.call_method(
            "Runtime.evaluate",
            expression="document.querySelector('.connect-button').click();"
        )
        wait_until_connected(tab)
    else:
        # logging.info("Already connected.")
        reconnect(tab)


def reconnect(tab: pychrome.Tab):
    """
    Reconnect: disconnect first if connected, then connect again.
    """
    status = get_connection_status(tab)
    logging.info("Initial reconect status: %s", status)
    
    if status == "connected":
        logging.info("Clicking to disconnect first...")
        tab.call_method(
            "Runtime.evaluate",
            expression="document.querySelector('.connect-button').click();"
        )

        # Wait until status becomes disconnected
        start = time.time()
        while time.time() - start < 10:
            if get_connection_status(tab) == "disconnected":
                logging.info("Disconnected, now reconnecting...")
                break
            time.sleep(1)

    # Now connect again
    connect(tab)


def main():
    EXTENSION_ID = "majdfhpaihoncoakbjgbdhglocklcgno"

    browser = init_browser()
    open_extension_popup()

    extension_tab = find_extension_tab(browser, EXTENSION_ID)
    if not extension_tab:
        logging.error("Could not locate extension popup. Exiting.")
        return

    # Example usage:
    connect(extension_tab)
    # reconnect(extension_tab)


if __name__ == "__main__":
    main()
