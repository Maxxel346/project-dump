# app.py
import threading
import time
import traceback
from flask import Flask, render_template, request, jsonify
import re
import os
import requests
import base64
from bs4 import BeautifulSoup
from tqdm import tqdm
import json
import pychrome  

app = Flask(__name__)

# --- Global state to store progress/logs ---
download_logs = []
download_status = "idle"  # idle, running, done, error
download_progress = 0  # optional percent for Gofile/Mediafire

# --- Utilities --- #
def log(msg):
    print(msg)
    download_logs.append(msg)

def reset_state():
    global download_logs, download_status, download_progress
    download_logs = []
    download_status = "idle"
    download_progress = 0

### --- Mediafire Downloader --- ###
def decode_base64(encoded_str: str) -> str:
    decoded_bytes = base64.b64decode(encoded_str)
    decoded_str = decoded_bytes.decode('utf-8')
    return decoded_str

def stream_download(url, file_path):
    try:
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            total_size = int(r.headers.get("Content-Length", 0))
            chunk_size = 1024 * 1024
            with open(file_path, "wb") as f:
                downloaded = 0
                start_time = time.time()
                for chunk in r.iter_content(chunk_size=chunk_size):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        elapsed = time.time() - start_time
                        speed = (downloaded / elapsed / (1024*1024)) if elapsed > 0 else 0
                        global download_progress
                        if total_size > 0:
                            download_progress = int(downloaded / total_size * 100)
                        log(f"[Mediafire] Downloading {file_path}: {download_progress}% | {speed:.2f} MB/s")
        log(f"[Mediafire] Download completed: {file_path}")
    except Exception as e:
        log(f"[Mediafire] Error: {e}")
        raise

def mediafire_downloader(url):
    log(f"[Mediafire] Starting download from {url}")
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    download_tag = soup.find('a', {'id': 'downloadButton'})
    if not download_tag or not download_tag.has_attr('data-scrambled-url'):
        raise Exception("Could not find download link on Mediafire page.")
    encoded_url = download_tag['data-scrambled-url']
    download_url = decode_base64(encoded_url)
    filename = url.split("/")[-1]
    log(f"[Mediafire] Resolved download URL: {download_url}")
    stream_download(download_url, filename)

### --- Gofile downloader --- ###
def get_gofile_id_from_url(url: str):
    patterns = [
        r"gofile\.io/d/([A-Za-z0-9_-]+)",
        r"/d/([A-Za-z0-9_-]+)"
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    raise ValueError("Invalid Gofile URL format")

def get_gofile_account_token():
    resp = requests.post("https://api.gofile.io/accounts")
    data = resp.json()
    if data.get("status") == "ok":
        token = data.get("data", {}).get("token")
        log(f"[Gofile] Obtained account token: {token}")
        return token
    else:
        raise Exception(f"Error getting gofile account: {data.get('message', 'No message')}")

def get_gofile_file_list(folder_id: str, token: str):
    url = f"https://api.gofile.io/contents/{folder_id}"
    headers = {"Authorization": f"Bearer {token}"}
    response = requests.get(url, headers=headers)
    data = response.json()
    if data.get("status") == "ok":
        return data.get("data", {})
    else:
        raise Exception(f"Gofile contents error: {data.get('message')}")

def download_file(url: str, filename: str):
    log(f"[Gofile] Downloading file {filename} from {url}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("Content-Length", 0))
        chunk_size = 1024 * 1024  # 1 MB
        downloaded = 0
        start_time = time.time()
        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    elapsed = time.time() - start_time
                    speed = (downloaded / elapsed / (1024*1024)) if elapsed > 0 else 0
                    global download_progress
                    if total_size > 0:
                        download_progress = int(downloaded / total_size * 100)
                    log(f"[Gofile] {filename}: {download_progress}% | {speed:.2f} MB/s")
    log(f"[Gofile] Download completed: {filename}")

def gofile_downloader(url: str):
    log(f"[Gofile] Starting download from {url}")
    folder_id = get_gofile_id_from_url(url)
    token = get_gofile_account_token()
    content = get_gofile_file_list(folder_id, token)
    if 'children' not in content or len(content["children"]) == 0:
        raise Exception("No files found in Gofile folder")
    for file_id, file_info in content["children"].items():
        if file_info.get("type") == "file":
            filename = file_info["name"]
            file_url = file_info["link"]
            download_file(file_url, filename)
        else:
            log(f"[Gofile] Skipping non-file item: {file_info.get('name')}")

### --- Pixeldrain downloader integration --- ###

TARGET_WS = "wss://pixeldrain.com/api/file_stats"
CHROME_URL = "http://127.0.0.1:9222"

ws_map = {}
transfer_limit_used = None
transfer_limit = None
file_size = None

def try_parse_payload(payload):
    if not isinstance(payload, str):
        return payload
    try:
        import json
        return json.loads(payload)
    except Exception:
        try:
            decoded = base64.b64decode(payload)
            return json.loads(decoded.decode("utf-8", errors="ignore"))
        except Exception:
            return payload

from bs4 import BeautifulSoup
import json5

def extract_viewer_data(html):
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
        log(f"[Pixeldrain] Failed to parse viewer_data: {e}")
        return None

from threading import Event

stop_event = Event()

def on_ws_created(requestId=None, url=None, **_):
    if url == TARGET_WS:
        ws_map[requestId] = url
        log(f"[Pixeldrain][WS] Tracking socket {url}")

def on_ws_closed(requestId=None, **_):
    if requestId in ws_map:
        log(f"[Pixeldrain][WS] Closed socket id {requestId}")
        del ws_map[requestId]

def on_ws_frame_received(requestId=None, response=None, **_):
    global transfer_limit_used, transfer_limit
    if requestId not in ws_map:
        return
    payload = response.get("payloadData")
    opcode = response.get("opcode")
    parsed = None
    if opcode == 1:
        parsed = try_parse_payload(payload)
    elif opcode == 2:
        try:
            raw = base64.b64decode(payload)
            parsed = json.loads(raw.decode("utf-8", errors="ignore"))
        except Exception:
            parsed = payload
    if isinstance(parsed, dict):
        if parsed.get("type") == "limits":
            log("[Pixeldrain] WebSocket limits message detected")
        limits = parsed.get("limits", {})
        transfer_limit_used = limits.get("transfer_limit_used", transfer_limit_used)
        transfer_limit = limits.get("transfer_limit", transfer_limit)
        if transfer_limit is not None:
            stop_event.set()

def on_ws_frame_sent(requestId=None, response=None, **_):
    pass

def pixeldrain_downloader(url: str) -> bool:
    global transfer_limit_used, transfer_limit, file_size, ws_map
    transfer_limit_used = None
    transfer_limit = None
    file_size = None
    ws_map = {}
    stop_event.clear()

    browser = pychrome.Browser(url=CHROME_URL)
    tab = browser.new_tab()

    tab.Network.webSocketCreated = on_ws_created
    tab.Network.webSocketClosed = on_ws_closed
    tab.Network.webSocketFrameReceived = on_ws_frame_received
    tab.Network.webSocketFrameSent = on_ws_frame_sent

    try:
        tab.start()
        tab.Network.enable()
        tab.Page.enable()
        log(f"[Pixeldrain] Navigating to {url}")
        tab.Page.navigate(url=url)
        time.sleep(5)
        html = tab.Runtime.evaluate(expression="document.documentElement.outerHTML")["result"]["value"]
        data = extract_viewer_data(html)
        if data and "api_response" in data:
            file_size = data["api_response"].get("size")
            log(f"[Pixeldrain] File size detected: {file_size} bytes")
        else:
            log("[Pixeldrain] Could not extract viewer data")

        while not stop_event.is_set():
            time.sleep(0.5)
            if transfer_limit_used is not None:
                log(f"[Pixeldrain] Transfer limit used so far: {transfer_limit_used}")
                stop_event.set()

        log(f"[Pixeldrain] Transfer limit: {transfer_limit}, used: {transfer_limit_used}")

        if all(v is not None for v in (file_size, transfer_limit, transfer_limit_used)):
            remaining = transfer_limit - transfer_limit_used
            if remaining > file_size:
                log("[Pixeldrain] Sufficient transfer limit, starting download.")
                result = tab.Runtime.evaluate(expression="""
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
                log(f"[Pixeldrain] Download button click result: {result['result']['value']}")
                # Sleep to allow download to start
                time.sleep(8)
                tab.stop()
                browser.close_tab(tab)
                log("[Pixeldrain] Download triggered. Check your browser downloads folder.")
                return True
            else:
                log("[Pixeldrain] Insufficient transfer limit. Consider VPN reconnect.")
                return False
        else:
            log("[Pixeldrain] Not enough data to evaluate transfer limits.")
            return False
    except Exception as e:
        log(f"[Pixeldrain] Exception: {e}\n{traceback.format_exc()}")
        return False
    finally:
        try:
            tab.stop()
            browser.close_tab(tab)
        except Exception:
            pass

# --- Link detection ---
def detect_service(url: str) -> str:
    url = url.lower()
    if "mediafire.com" in url:
        return "mediafire"
    elif "gofile.io" in url:
        return "gofile"
    elif "pixeldrain.com" in url:
        return "pixeldrain"
    else:
        return "unknown"

# --- Background download worker ---
def download_worker(url):
    global download_status, download_progress
    reset_state()
    download_status = "running"
    download_progress = 0
    try:
        service = detect_service(url)
        log(f"[System] Detected service: {service}")
        if service == "mediafire":
            mediafire_downloader(url)
        elif service == "gofile":
            gofile_downloader(url)
        elif service == "pixeldrain":
            success = pixeldrain_downloader(url)
            if not success:
                log("[System] Pixeldrain download failed or incomplete.")
        else:
            log("[System] Unsupported URL / service.")
            download_status = "error"
            return
        download_status = "done"
    except Exception as e:
        log(f"[System] Download exception: {e}\n{traceback.format_exc()}")
        download_status = "error"

# --- Flask routes ---
@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", status=download_status, progress=download_progress, logs=download_logs)

@app.route("/start_download", methods=["POST"])
def start_download():
    url = request.form.get("url")
    if not url:
        return jsonify({"status": "error", "message": "No URL provided"})
    if download_status == "running":
        return jsonify({"status": "error", "message": "Download already in progress"})

    thread = threading.Thread(target=download_worker, args=(url,))
    thread.daemon = True
    thread.start()

    return jsonify({"status": "ok", "message": "Download started"})

@app.route("/status", methods=["GET"])
def status():
    global download_status, download_progress, download_logs
    return jsonify({
        "status": download_status,
        "progress": download_progress,
        "logs": download_logs[-20:]  # last 20 logs
    })

if __name__ == "__main__":
    # Run flask app
    app.run(host="0.0.0.0", port=5000, debug=True)
