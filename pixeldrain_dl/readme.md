# pixeldrain_dl

A Python automation tool to **sniff Pixeldrain WebSocket traffic** and determine whether a file can be downloaded within the current transfer limit.  
If the transfer quota is insufficient, it can automatically **reconnect a VPN extension (Veepn)** to reset the quota and retry.

---

## ✨ Features

- Uses **Chrome DevTools Protocol** (via [pychrome](https://github.com/fate0/pychrome)) to:
  - Capture Pixeldrain WebSocket traffic.
  - Extract file size and transfer limits.
  - Decide whether a file can be downloaded within the remaining quota.
- Automates clicking the **download button** when enough quota is available.
- Integrates with **Veepn Chrome extension** to reconnect automatically when quota runs out.
- Parses `window.viewer_data` from Pixeldrain pages for file metadata.
- Logging for all major events (WebSocket, connection state, VPN handling).

---

## 📂 Project Structure

```
pixeldrain_dl/
│
├── sniff_pixeldrain_ws.py   # Core Pixeldrain WebSocket sniffer
├── extensionVeepn.py        # Veepn extension automation (connect/reconnect)
└── README.md                # Project documentation
```

---

## ⚙️ Requirements

- Python 3.8+
- Google Chrome (with **remote debugging** enabled: `--remote-debugging-port=9222`)
- Veepn extension installed in Chrome (ID: `majdfhpaihoncoakbjgbdhglocklcgno`)

### Python dependencies
Install required libraries:

```bash
pip install pychrome pyautogui beautifulsoup4 json5
```

---

## 🚀 Usage

### 1. Start Chrome with debugging enabled
```bash
chrome.exe --remote-debugging-port=9222 --user-data-dir="C:\ChromeDebug"
```

### 2. Run the sniffer
```bash
python sniff_pixeldrain_ws.py
```

The script will:
1. Navigate to a Pixeldrain file URL.
2. Extract file size and quota usage from WebSocket frames.
3. Decide if download is possible.
4. Click the **download button** if enough quota is available.
5. If not, trigger Veepn reconnection and retry.

---

## 🔄 VPN Automation

The `extensionVeepn.py` module:
- Opens the Veepn extension popup (`Ctrl+Shift+H`).
- Detects whether it’s **connected** or **disconnected**.
- Supports:
  - `connect()` → connects if disconnected.
  - `reconnect()` → disconnects first, then reconnects.
- Waits until VPN is fully connected before resuming download attempts.

---

## 📝 Example Logs

```
2025-09-27 13:12:50,632 [INFO] Connecting to Chrome at http://127.0.0.1:9222
2025-09-27 13:12:55,760 [INFO] Navigating to https://pixeldrain.com/u/UaZMK2SQ
2025-09-27 13:12:57,544 [INFO] Detected file size: 104857600 bytes
2025-09-27 13:13:00,102 [INFO] Transfer limit used so far: 51200000 bytes
2025-09-27 13:13:00,103 [INFO] [OK] Download can complete within transfer limit.
2025-09-27 13:13:00,104 [INFO] Clicked download button.
```

---

## ⚠️ Disclaimer

This project is for **educational and personal use only**.  
Automating file downloads or bypassing limits may violate Pixeldrain’s Terms of Service. Use responsibly.
