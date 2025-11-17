# uploader.py
import os
import requests
from requests.auth import HTTPBasicAuth

# === Custom Exceptions ===


class UploadError(Exception):
    """Base upload exception."""


class PixelDrainError(UploadError):
    """Raise for PixelDrain related errors."""


class GoFileError(UploadError):
    """Raise for GoFile related errors."""


class MixDropError(UploadError):
    """Raise for MixDrop related errors."""


# === PixelDrain Upload ===


def upload_pixeldrain(file_path: str, api_key: str) -> dict:
    """
    Uploads a file to PixelDrain using API key (Basic Auth password).

    Args:
        file_path (str): Path to the file to upload.
        api_key (str): PixelDrain API key.

    Returns:
        dict: {
            "provider": "pixeldrain",
            "id": "<file_id>",
            "name": "<filename>"
        }

    Raises:
        FileNotFoundError: if file_path does not exist.
        PixelDrainError: descriptive errors on upload failure.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File '{file_path}' does not exist or is not a file.")

    filename = os.path.basename(file_path)
    if len(filename) > 255:
        raise PixelDrainError("File Name is too long, Max 255 characters allowed.")

    url = f"https://pixeldrain.com/api/file/{filename}"
    auth = HTTPBasicAuth("", api_key)  # username empty, api_key as password

    with open(file_path, "rb") as f:
        file_bytes = f.read()

    headers = {
        "Content-Type": "application/octet-stream",
    }

    try:
        resp = requests.put(url, auth=auth, headers=headers, data=file_bytes, timeout=60)
    except requests.RequestException as e:
        raise PixelDrainError(f"Request to PixelDrain failed: {e}") from e

    if resp.status_code == 201:
        # success, expect JSON { "id": "abc123" }
        try:
            data = resp.json()
        except Exception as e:
            raise PixelDrainError(f"Unexpected non-JSON response with HTTP 201: {resp.text}") from e
        file_id = data.get("id")
        if not file_id:
            raise PixelDrainError("PixelDrain response missing 'id' field.")
        return {"provider": "pixeldrain", "id": file_id, "name": filename}

    # handle known errors by response codes and JSON body based on docs
    try:
        err = resp.json()
    except Exception:
        err = {}

    # map specific codes to errors
    if resp.status_code == 422:
        if err.get("value") == "no_file":
            raise PixelDrainError("The file does not exist or is empty.")
    if resp.status_code == 413:
        if err.get("value") == "file_too_large":
            raise PixelDrainError("The file you tried to upload is too large.")
        if err.get("value") == "name_too_long":
            raise PixelDrainError("File Name is too long, Max 255 characters allowed.")
    if resp.status_code == 500:
        if err.get("value") == "internal":
            raise PixelDrainError("An internal server error occurred on PixelDrain.")
        if err.get("value") == "writing":
            raise PixelDrainError("PixelDrain server may be out of storage space.")

    # fallback unknown error
    raise PixelDrainError(
        f"PixelDrain upload failed: HTTP {resp.status_code} - {err.get('message', resp.text)}"
    )


# === GoFile Upload ===


def upload_gofile(file_path: str) -> dict:
    """
    Uploads a file anonymously to GoFile.io.

    Args:
        file_path (str): Path to the file to upload.

    Returns:
        dict: {
            "provider": "gofile",
            "downloadPage": "...",
            "folderId": "...",
            "token": "..."
        }

    Raises:
        FileNotFoundError: if file_path does not exist.
        GoFileError: if upload status is not "ok" or request fails.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File '{file_path}' does not exist or is not a file.")

    upload_endpoint = "https://upload.gofile.io/uploadFile"

    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}

        try:
            resp = requests.post(upload_endpoint, files=files, timeout=60)
        except requests.RequestException as e:
            raise GoFileError(f"Request to GoFile failed: {e}") from e

    try:
        data = resp.json()
    except Exception as e:
        raise GoFileError(f"GoFile returned non-JSON response: {resp.text}") from e

    if data.get("status") != "ok":
        raise GoFileError(f"GoFile upload failed: status != ok - {data}")

    d = data.get("data") or {}
    download_page = d.get("downloadPage")
    folder_id = d.get("parentFolder")
    token = d.get("guestToken")

    return {
        "provider": "gofile",
        "downloadPage": download_page,
        "folderId": folder_id,
        "token": token,
    }


# === MixDrop Upload ===


def upload_mixdrop(file_path: str, email: str, api_key: str, folder: str | None = None) -> dict:
    """
    Uploads a file to MixDrop API with API email + key, optionally with folder.

    Args:
        file_path (str): Path to the file to upload.
        email (str): API email for MixDrop.
        api_key (str): API key for MixDrop.
        folder (str | None): Optional folder ID.

    Returns:
        dict: {
            "provider": "mixdrop",
            "fileref": "...",
            "url": "...",
            "embedurl": "..."
        }

    Raises:
        FileNotFoundError: if file_path does not exist.
        MixDropError: if upload fails or missing keys.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File '{file_path}' does not exist or is not a file.")

    url = "https://ul.mixdrop.ag/api"

    data = {
        "email": email,
        "key": api_key,
    }
    if folder is not None:
        data["folder"] = folder

    with open(file_path, "rb") as f:
        files = {
            "file": (os.path.basename(file_path), f),
        }

        try:
            resp = requests.post(url, data=data, files=files, timeout=120)
        except requests.RequestException as e:
            raise MixDropError(f"Request to MixDrop failed: {e}") from e

    try:
        j = resp.json()
    except Exception as e:
        raise MixDropError(f"MixDrop returned non-JSON response: {resp.text}") from e

    if not isinstance(j, dict) or "success" not in j:
        raise MixDropError(f"Invalid MixDrop response structure: {j}")

    if j["success"] is not True:
        raise MixDropError(f"MixDrop upload failed: {j}")

    result = j.get("result")
    if not result:
        raise MixDropError("MixDrop upload failed: missing 'result' in response.")

    fileref = result.get("fileref")
    url_ = result.get("url")
    embedurl = result.get("embedurl")

    if not fileref or not url_ or not embedurl:
        raise MixDropError("MixDrop upload failed: incomplete upload info in response.")

    return {
        "provider": "mixdrop",
        "fileref": fileref,
        "url": url_,
        "embedurl": embedurl,
    }


# === Usage Examples ==

if __name__ == "__main__":
    import pprint

    print("=== Example: Upload PixelDrain ===")
    try:
        # Replace with an actual file path and your PixelDrain API key
        pixeldrain_res = upload_pixeldrain("example_file.txt", "your_pixeldrain_api_key_here")
        pprint.pprint(pixeldrain_res)
    except Exception as e:
        print(f"PixelDrain Upload Failed: {e}")

    print("\n=== Example: Upload GoFile ===")
    try:
        # Replace with an actual file path
        gofile_res = upload_gofile("example_file.txt")
        pprint.pprint(gofile_res)
    except Exception as e:
        print(f"GoFile Upload Failed: {e}")

    print("\n=== Example: Upload MixDrop ===")
    try:
        # Replace with actual file path, MixDrop api email and api key
        mixdrop_res = upload_mixdrop("example_file.txt", "user@example.com", "your_mixdrop_api_key")
        pprint.pprint(mixdrop_res)
    except Exception as e:
        print(f"MixDrop Upload Failed: {e}")

# === End of uploader.py ===
