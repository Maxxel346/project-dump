import sys
import re
import base64
import requests
from bs4 import BeautifulSoup
from tqdm import tqdm
import json
import time

### --- Mediafire Downloader --- ###
def decode_base64(encoded_str: str) -> str:
    decoded_bytes = base64.b64decode(encoded_str)
    decoded_str = decoded_bytes.decode('utf-8')
    return decoded_str

def mediafire_downloader(url: str):
    print(f"[Mediafire] Downloading from {url}")
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    download_tag = soup.find('a', {'id': 'downloadButton'})
    if not download_tag or not download_tag.has_attr('data-scrambled-url'):
        raise Exception("Could not find download link on Mediafire page.")
    encoded_url = download_tag['data-scrambled-url']
    download_url = decode_base64(encoded_url)
    print(f"[Mediafire] Resolved download URL: {download_url}")
    stream_download(download_url)

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
    # Get free account token to avoid rate limit
    resp = requests.post("https://api.gofile.io/accounts")
    data = resp.json()
    if data.get("status") == "ok":
        token = data.get("data", {}).get("token")
        print(f"[Gofile] Obtained account token: {token}")
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
    print(f"[Download] Downloading {filename} from {url}")
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("Content-Length", 0))
        chunk_size = 1024 * 1024  # 1 MB
        progress = tqdm(total=total_size, unit='B', unit_scale=True, desc=filename)
        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    progress.update(len(chunk))
        progress.close()
    print(f"[Download] Finished {filename}")

def gofile_downloader(url: str):
    folder_id = get_gofile_id_from_url(url)
    token = get_gofile_account_token()
    # List files/folders in the folder
    content = get_gofile_file_list(folder_id, token)
    if 'children' not in content or len(content["children"]) == 0:
        raise Exception("No files found in Gofile folder")
    # Download all files sequentially
    for file_id, file_info in content["children"].items():
        if file_info.get("type") == "file":
            filename = file_info["name"]
            file_url = file_info["link"]
            download_file(file_url, filename)
        else:
            print(f"Skipping non-file item: {file_info.get('name')}")

### --- Pixeldrain downloader stub --- ###

def pixeldrain_downloader(url: str):
    print("[Pixeldrain] Complex downloader detected. For now, open URL manually:")
    print(f" -> {url}")
    # ...........

### --- Link Detection --- ###
def detect_service(url: str):
    url = url.lower()
    if "mediafire.com" in url:
        return "mediafire"
    elif "gofile.io" in url:
        return "gofile"
    elif "pixeldrain.com" in url:
        return "pixeldrain"
    else:
        return "unknown"

### --- Entry --- ###
def main():
    if len(sys.argv) < 2:
        print("Usage: python download.py <url>")
        sys.exit(1)
    url = sys.argv[1]

    service = detect_service(url)
    print(f"Detected service: {service}")

    try:
        if service == "mediafire":
            mediafire_downloader(url)
        elif service == "gofile":
            gofile_downloader(url)
        elif service == "pixeldrain":
            pixeldrain_downloader(url)
        else:
            print("Unsupported URL or service not recognized.")
    except Exception as e:
        print(f"Error during download: {e}")

if __name__ == "__main__":
    main()
