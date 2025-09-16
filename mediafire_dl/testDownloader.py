import requests
from tqdm import tqdm
import threading
import time
import os

class Downloader:
    def __init__(self, id, url, position, filename=None, chunk_size=1024*512):
        self.id = id
        self.url = url
        self.filename = filename or os.path.basename(url.split("?")[0])
        self.chunk_size = chunk_size
        self._stop_flag = False
        self._thread = None
        self.position = position  # tqdm line position

    def _download_worker(self):
        try:
            with requests.get(self.url, stream=True) as r:
                r.raise_for_status()
                total_size = int(r.headers.get("Content-Length", 0))

                with open(self.filename, "wb") as f, tqdm(
                    total=total_size,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=f"ID {self.id}: {self.filename}",
                    position=self.position,
                    leave=True,
                    dynamic_ncols=True,
                ) as progress:
                    start_time = time.time()
                    downloaded = 0

                    for chunk in r.iter_content(chunk_size=self.chunk_size):
                        if self._stop_flag:
                            tqdm.write(f"🛑 Download {self.id} stopped.")
                            return

                        if chunk:
                            f.write(chunk)
                            progress.update(len(chunk))
                            downloaded += len(chunk)

                            elapsed = time.time() - start_time
                            if elapsed > 0:
                                speed = downloaded / elapsed / (1024 * 1024)
                                progress.set_postfix_str(f"{speed:.2f} MB/s")

            tqdm.write(f"✅ Download {self.id} completed!")

        except Exception as e:
            tqdm.write(f"❌ Error in download {self.id}: {e}")

    def start(self):
        self._stop_flag = False
        self._thread = threading.Thread(target=self._download_worker, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_flag = True


class DownloadManager:
    def __init__(self):
        self.downloads = {}
        self.lock = threading.Lock()
        self.next_id = 1
        self.next_position = 0  # tqdm position tracker

    def add_download(self, url, filename=None):
        with self.lock:
            download_id = self.next_id
            self.next_id += 1
            pos = self.next_position
            self.next_position += 1
        d = Downloader(download_id, url, pos, filename)
        self.downloads[download_id] = d
        d.start()
        return download_id

    def stop_download(self, download_id):
        if download_id in self.downloads:
            self.downloads[download_id].stop()
        else:
            print(f"⚠️ No download with ID {download_id}")

    def stop_all(self):
        for d in self.downloads.values():
            d.stop()



if __name__ == "__main__":
    manager = DownloadManager()

    id1 = manager.add_download("https://download2350.mediafire.com/xxxxx-xxxxxxxxxxxxxxxxxxxxxxxxxxx-xxxxxxxxxxxxxxxxxx-xxxxxxxxxxx/yyyyyyyyyyy/zzzzzzzzzz-pc.zip")
    id2 = manager.add_download("https://download2274.mediafire.com/xxxxxxxxxxxxx-xxxxxxxxxxxxxxxxxxxxxxxxx-xxxxxxxxxxxxxx/yyyyyyyyyyyyyyy/zzzzzzz-ANDROID.apk")

    time.sleep(3)

    id3 = manager.add_download("https://download1503.mediafire.com/xxxxxxxxxxxxxxxxxxxxxxx/yyyyyyyyyyyyyyy/zzzzzzz.zip")