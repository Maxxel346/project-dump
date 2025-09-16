import requests
from bs4 import BeautifulSoup
import base64
import time
from tqdm import tqdm

# Decode base 64 function
def decode_base64(encoded_str):
    decoded_bytes = base64.b64decode(encoded_str)
    decoded_str = decoded_bytes.decode('utf-8')
    return decoded_str


def stream_download_mediafire(url):
    filename = url.split("/")[-1]

    # Stream download
    with requests.get(url, stream=True) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("Content-Length", 0))
        chunk_size = 1024  # 1 KB
        progress = tqdm(
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=filename,
        )

        start_time = time.time()
        downloaded = 0

        with open(filename, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:  # filter out keep-alive
                    f.write(chunk)
                    progress.update(len(chunk))
                    downloaded += len(chunk)

                    # Show speed (MB/s)
                    elapsed = time.time() - start_time
                    if elapsed > 0:
                        speed = downloaded / elapsed / (1024 * 1024)
                        progress.set_postfix_str(f"{speed:.2f} MB/s")

        progress.close()

# Mediafire download function
def mediafire_downloader(link):
    response = requests.get(link)
    # print(response.text)
    soup = BeautifulSoup(response.text, 'html.parser')
    download_link = soup.find('a', {'id': 'downloadButton'})['data-scrambled-url']
    # print("Encoded Download link:", download_link)
    decoded_url = decode_base64(download_link)
    print("Decoded Download link:", decoded_url)
    stream_download_mediafire(decoded_url)
    # print("Downloaded")



link = "https://www.mediafire.com/file_premium/xxxxxxxxxxxxxxxxxx/yyyyyyyyyyyyy-zzzzzzz-pc.zip"
mediafire_downloader(link)

