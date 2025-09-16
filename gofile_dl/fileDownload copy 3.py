import requests
from bs4 import BeautifulSoup
import json
import time
from tqdm import tqdm


def get_gofile_id_from_url(url):
    """
    Extract the Gofile ID from a given URL.
    """
    if "/d/" in url:
        return url.split("/d/")[-1].split("/")[0]
    elif "gofile.io/d/" in url:
        return url.split("gofile.io/d/")[-1].split("/")[0]
    else:
        raise ValueError("Invalid Gofile URL format")
def get_gofile_account_info():
    url = "https://api.gofile.io/accounts"
    response = requests.post(url)
    # print(response.status_code)
    return response.json()


def get_gofile_file_list(gofile_id, token, bearer_token=None):
    url = f"https://api.gofile.io/contents/{gofile_id}"
    params = {
        "wt": token,
        "contentFilter": "",
        "page": 1,
        "pageSize": 1000,
        "sortField": "name",
        "sortDirection": 1
    }
    # bearer token in header
    headers = {
        "Authorization": f"Bearer {bearer_token}" if bearer_token else f"Bearer {token}"
    }
    response = requests.get(url, params=params, headers=headers)
    data = response.json()
    if data.get("status") == "ok":
        # return data.get("data", {}).get("children", [])
        return data.get("data", {})
    else:
        raise Exception(f"Error fetching file list: {data.get('message', 'Unknown error')}")
    

def download_gofile_file(file_url, output_path, account_token=None):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Referer": "https://gofile.io/",
    }
    cookies = {}
    print(headers)
    cookies = {}
    if account_token:
        cookies["accountToken"] = account_token

    # allow_redirects=True makes requests follow the 302 to the real file
    with requests.get(file_url, headers=headers, cookies=cookies,
                      stream=True, allow_redirects=True) as r:
        r.raise_for_status()
        total_size = int(r.headers.get("Content-Length", 0))
        chunk_size = 1024 * 1024  # 1 MB
        progress = tqdm(
            total=total_size,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=output_path,
        )

        with open(output_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if chunk:
                    f.write(chunk)
                    progress.update(len(chunk))

        progress.close()

    print(f"Downloaded {output_path}")


# def download_gofile_file(direct_url, output_path, retry_count=3, retry_delay=5):
#     """
#     Downloads a file from Gofile using the direct URL.
#     """
#     print(f"[DEBUG] Starting download attempt for: {direct_url}")
#     for attempt in range(retry_count):
#         try:
#             response = requests.get(direct_url, stream=True, timeout=30)

#             # Debug output
#             print(f"[DEBUG] Attempt {attempt+1}: HTTP {response.status_code}")
#             print(f"[DEBUG] Response headers: {response.headers}")
#             try:
#                 print(f"[DEBUG] Response text (first 500 chars): {response.text[:500]}")
#                 with open("debug_response.html", "w", encoding="utf-8") as f:
#                     f.write(response.text)
#             except Exception as e:
#                 print(f"[DEBUG] Could not read response.text: {e}")

        #     response.raise_for_status()

        #     # Write to file
        #     with open(output_path, 'wb') as f:
        #         for chunk in response.iter_content(chunk_size=8192):
        #             if chunk:
        #                 f.write(chunk)

        #     print(f"Downloaded: {output_path}")
        #     return
        # except Exception as e:
        #     print(f"Attempt {attempt+1} failed: {e}")
        #     if attempt < retry_count - 1:
        #         print(f"Retrying in {retry_delay} seconds...")
        #         time.sleep(retry_delay)
        #     else:
        #         print(f"Failed to download after {retry_count} attempts: {direct_url}")





    
account_info = get_gofile_account_info()
print("Account Token:", account_info.get("data", {}).get("token", "N/A"))
account_token = account_info.get("data", {}).get("token", "N/A")
file_id = get_gofile_id_from_url("https://gofile.io/d/--IDHERE--")
file_list = get_gofile_file_list(file_id, "4fd6sg89d7s6", account_token)
print(file_list)
with open("gofile_file_list.json", "w", encoding="utf-8") as f:
    json.dump(file_list, f, ensure_ascii=False, indent=4)
for file_id, file_info in file_list["children"].items():
    name = file_info.get("name")
    file_type = file_info.get("type")
    size = file_info.get("size")
    link = file_info.get("link")
    host = file_info.get("serverSelected")

    print(f"Name: {name}")
    print(f"Type: {file_type}")
    print(f"Size: {size} bytes")
    print(f"Link: {link}")
    print(f"Host: {host}")
    print("-" * 40)
    # download the file
    # download_gofile_file(link, name, host)
    download_gofile_file(link, name, account_token)
