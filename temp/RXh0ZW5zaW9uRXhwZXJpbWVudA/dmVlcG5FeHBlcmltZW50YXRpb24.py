import time
import random
import logging
import pychrome
import pyautogui


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)


def init_browser(debug_url: str = "http://127.0.0.1:9222", wait_time: int = 5) -> pychrome.Browser:
    """
    Initialize connection to Chrome remote debugging protocol.
    """
    logging.info("Connecting to Chrome at %s", debug_url)
    browser = pychrome.Browser(url=debug_url)
    time.sleep(wait_time)  # Give Chrome time to be ready
    return browser


def open_extension_popup():
    """
    Trigger Chrome extension popup using hotkey (Ctrl+Shift+H).
    """
    logging.info("Opening extension popup with hotkey...")
    pyautogui.hotkey("ctrl", "shift", "h")


def find_extension_tab(browser: pychrome.Browser, extension_id: str) -> pychrome.Tab:
    """
    Scan open tabs to find the extension popup by its unique identifier.
    """
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
                # 🔑 don't stop this tab — keep it alive for later use
                return tab

        except Exception as e:
            logging.error("Error scanning tab %d: %s", i, e)
            tab.stop()

    logging.warning("Extension tab not found.")
    return None


def click_connect_button(tab: pychrome.Tab):
    """
    Click the connect button inside the extension popup.
    """
    logging.info("Clicking connect button in extension tab...")
    tab.start()
    tab.Page.enable()

    tab.call_method(
        "Runtime.evaluate",
        expression="""
        var btn = document.querySelector('.connect-button');
        if(btn) { btn.click(); } else { console.log('Button not found'); }
        """
    )


def save_tab_html(tab: pychrome.Tab, prefix: str = "extension_tab"):
    """
    Save the full HTML content of the tab for debugging.
    """
    html = tab.call_method(
        "Runtime.evaluate",
        expression="document.documentElement.outerHTML"
    )["result"]["value"]

    file_id = random.randint(1, 50)
    filename = f"{prefix}_{file_id}.html"

    with open(filename, "w", encoding="utf-8") as f:
        f.write(html)

    logging.info("Saved tab HTML to %s", filename)


def main():
    EXTENSION_ID = "majdfhpaihoncoakbjgbdhglocklcgno"  # VPN extension identifier

    browser = init_browser()
    open_extension_popup()

    extension_tab = find_extension_tab(browser, EXTENSION_ID)

    if not extension_tab:
        logging.error("Could not locate extension popup. Exiting.")
        return

    click_connect_button(extension_tab)
    save_tab_html(extension_tab)


if __name__ == "__main__":
    main()
