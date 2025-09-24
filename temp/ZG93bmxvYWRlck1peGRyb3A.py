import pychrome
# http://127.0.0.1:9222
from bs4 import BeautifulSoup
import time

def get_browser():
    try:
        browser = pychrome.Browser(url="http://127.0.0.1:9222")
        return browser
    except Exception as e:
        print(f"Error connecting to Chrome: {e}")
        return None

def get_page_content(tab):
    html = tab.call_method("Runtime.evaluate", expression="document.documentElement.outerHTML")['result']['value']
    return html

def get_download_link_from_mixdrop(html):
    # .download-wrapper .download-btn
    soup = BeautifulSoup(html, 'html.parser')
    download_button = soup.select_one('.download-wrapper .download-btn')
    if download_button and download_button.has_attr('href'):
        return download_button['href']
    return None

def handle_new_target(**kwargs):
    target_info = kwargs.get("targetInfo", {})
    target_id = target_info.get("targetId")
    url = target_info.get("url", "")

    # If it's an ad tab/window (not the main site), just close it
    if "mixdrop" not in url:
        print(f"Closing ad tab: {url}")
        browser.call_method("Target.closeTarget", targetId=target_id)

if __name__ == "__main__":
    browser = get_browser()
    if browser:
        tab = browser.new_tab()
        tab.start()
        tab.Page.enable()
        tab.Network.enable()
        # xadsmart.com
        tab.Network.setBlockedURLs(
            urls=["*://c.adsco.re/*", "*://nu.rocklaymalope.com/*", "*://*.engirtjarless.life/*", "*://trudgeaskeses.qpon/*", "*://xadsmart.com/*"]
        )
        # Watch for new targets (popups/tabs)
        tab.set_listener("Target.targetCreated", handle_new_target)
        tab.call_method("Page.navigate", url="https://mixdrop.cv/f/xxxxxxxx")
        tab.wait(5)
        while True:
            download_link = get_download_link_from_mixdrop(get_page_content(tab))
            if download_link:
                print(f"Download link found: {download_link}")
                break
            else:
                print("Download link not found.")
                # click download button "beaware of ads.. it opens new tab or window"
                tab.call_method("Runtime.evaluate", expression="""
                var btn = document.querySelector('.download-btn');
                if(btn) { btn.click(); }
                """)
                time.sleep(3)
