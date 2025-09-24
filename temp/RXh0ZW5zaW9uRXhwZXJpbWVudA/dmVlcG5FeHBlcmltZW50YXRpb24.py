import pychrome
from bs4 import BeautifulSoup
import time
import pyautogui
browser = pychrome.Browser(url="http://127.0.0.1:9222")
time.sleep(5)  # Wait for Chrome to be fully ready
# send Ctrl + Shift + H
pyautogui.hotkey('ctrl', 'shift', 'h')
extension_tab_list = None
for i, tab in enumerate(browser.list_tab()):
    try:
        tab.start()
        tab.Page.enable()
        tab.Runtime.enable()

        # Quick DOM check: only grab <head>
        result = tab.Runtime.evaluate(
            expression="document.head.innerHTML",
            returnByValue=True
        )
        html = result["result"]["value"]

        if "majdfhpaihoncoakbjgbdhglocklcgno" in html: # VPN extension identifier
            print(f"Found VPN popup at tab {i}, id={tab.id}, url={tab.url}")
            extension_tab_list = i
            break

        tab.stop()
    except Exception as e:
        print("Error scanning tab:", e)
if extension_tab_list is None:
    print("Extension tab not found.")
    exit()
extension_tab = browser.list_tab()[extension_tab_list]
# extension_tab = browser.list_tab()[extension_tab_list]
if extension_tab:
    # get html content of the tab
    extension_tab.start()
    extension_tab.Page.enable()
    # click on .connect-button
    extension_tab.call_method("Runtime.evaluate", expression="""
    var btn = document.querySelector('.connect-button');
    if(btn) { btn.click(); } else { console.log('Button not found'); }
    """)
    import random
    ranID = random.randint(1, 50)
    # gett html content of the tab
    html = extension_tab.call_method("Runtime.evaluate", expression="document.documentElement.outerHTML")['result']['value']
    # save html to file for debugging
    with open(f"extension_tab_{ranID}.html", "w", encoding="utf-8") as f:
        f.write(html)
else:
    print("Extension tab not found.")