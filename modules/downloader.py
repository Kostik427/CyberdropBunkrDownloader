"""
downloader.py
=============

Contains functionality for processing a URL (or gallery page) to extract
downloadable items, managing concurrent downloads with retries, and exporting
a URL list if needed.

Functions:
    - process_url(...): Entry point for processing a single URL.
    - download_with_retries(...): Download a file with retry logic.
    - download(...): Perform the actual file download with a progress bar.
"""

import os
import time
from typing import Optional, Dict, Any, List
import requests
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor, as_completed
from modules import utils, url_handler


def process_url(
    session: requests.Session,
    cdn_list: Optional[List[str]],
    url: str,
    retries: int,
    extensions: str,
    only_export: bool,
    custom_path: Optional[str],
) -> None:
    """
    Process the given URL: extract items from the gallery page, filter by extension,
    and either export the list of download URLs or download the files concurrently.

    Args:
        session (requests.Session): Session for HTTP requests.
        cdn_list (Optional[List[str]]): List of CDN hosts.
        url (str): The URL to process.
        retries (int): Number of download retries.
        extensions (str): Comma-separated file extensions to filter downloads.
        only_export (bool): If True, only export the list of URLs.
        custom_path (Optional[str]): Custom download directory path.
    """
    # Determine the page type by inspecting the title.
    response = session.get(url)
    if response.status_code != 200:
        print(f"[-] HTTP error {response.status_code} for {url}")
        return

    from bs4 import BeautifulSoup  # Local import for clarity.

    soup = BeautifulSoup(response.content, "html.parser")
    title_text = soup.find("title").text if soup.find("title") else ""
    is_bunkr = "| Bunkr" in title_text

    # Decide the URL handler strategy.
    handler = url_handler.URLHandlerFactory.get_url_handler(is_bunkr)

    # For direct link pages vs. gallery pages:
    direct_link = False
    items: List[Any] = []
    if is_bunkr:
        # Check if the page is a direct link page.
        direct_link = bool(
            soup.find("span", {"class": "ic-videos"})
            or soup.find("div", {"class": "lightgallery"})
        )
        if direct_link:
            album_name_elem = soup.find("h1", {"class": "text-[20px]"}) or soup.find(
                "h1", {"class": "truncate"}
            )
            album_name = (
                utils.remove_illegal_chars(album_name_elem.text)
                if album_name_elem
                else "unknown_album"
            )
            items.append(
                {"url": handler.get_real_download_url(session, cdn_list, url)["url"]}
            )
        else:
            album_name_elem = soup.find("h1", {"class": "truncate"})
            album_name = (
                utils.remove_illegal_chars(album_name_elem.text)
                if album_name_elem
                else "unknown_album"
            )
            # Assume gallery items are contained in <a class="after:absolute">.
            boxes = soup.find_all("a", {"class": "after:absolute"})
            for box in boxes:
                items.append({"url": box["href"]})
    else:
        album_name_elem = soup.find("h1", {"id": "title"})
        album_name = (
            utils.remove_illegal_chars(album_name_elem.text)
            if album_name_elem
            else "unknown_album"
        )
        items_dom = soup.find_all("a", {"class": "image"})
        for item_dom in items_dom:
            items.append({"url": f"https://cyberdrop.me{item_dom['href']}"})

    download_path = utils.get_and_prepare_download_path(custom_path, album_name)
    already_downloaded = utils.get_already_downloaded_url(download_path)
    extensions_list = (
        [ext.strip() for ext in extensions.split(",")] if extensions else []
    )

    download_tasks = []
    for item in items:
        # If not a direct link, resolve the real download URL.
        if not direct_link:
            real_item = handler.get_real_download_url(session, cdn_list, item["url"])
            if not real_item:
                print("\t[-] Unable to resolve a valid download URL.")
                continue
            item = real_item

        url_data = utils.get_url_data(item["url"])
        if (not extensions_list or url_data["extension"] in extensions_list) and item[
            "url"
        ] not in already_downloaded:
            if only_export:
                utils.write_url_to_list(item["url"], download_path)
            else:
                download_tasks.append(
                    {
                        "url": item["url"],
                        "name": item.get("name"),
                        "is_bunkr": is_bunkr,
                        "retries": retries,
                    }
                )

    if only_export:
        print(
            f"\t[+] URL list exported to {os.path.join(download_path, 'url_list.txt')}"
        )
    else:
        if download_tasks:
            max_workers = min(10, len(download_tasks))
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_task = {
                    executor.submit(
                        download_with_retries, session, task, download_path, cdn_list
                    ): task
                    for task in download_tasks
                }
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        future.result()
                    except Exception as exc:
                        print(f"\t[-] Error processing {task['url']}: {exc}")
        print("\t[+] Download processing completed.")


def download_with_retries(
    session: requests.Session,
    task: Dict[str, Any],
    download_path: str,
    cdn_list: Optional[list],
) -> None:
    """
    Download a file with a specified number of retries.

    Args:
        session (requests.Session): Session for HTTP requests.
        task (dict): Download task details (url, name, is_bunkr, retries).
        download_path (str): Destination folder.
        cdn_list (Optional[list]): List of CDN hosts.
    """
    url = task["url"]
    retries = task["retries"]
    is_bunkr = task["is_bunkr"]
    file_name = task.get("name")  # May be None; it will be derived if so.

    for attempt in range(1, retries + 1):
        try:
            print(f"\t[+] Downloading {url} (Attempt {attempt}/{retries})")
            download(session, url, download_path, is_bunkr, file_name)
            break  # Success: exit retry loop.
        except requests.RequestException as e:
            if attempt < retries:
                time.sleep(2)
            else:
                print(f"\t[-] Failed to download {url} after {retries} attempts: {e}")
        except Exception as e:
            print(f"\t[-] Unexpected error downloading {url}: {e}")
            break


def download(
    session: requests.Session,
    item_url: str,
    download_path: str,
    is_bunkr: bool = False,
    file_name: Optional[str] = None,
) -> None:
    """
    Download the file from item_url into download_path, displaying a progress bar.

    Args:
        session (requests.Session): Session for HTTP requests.
        item_url (str): The URL of the file to download.
        download_path (str): Directory where the file will be saved.
        is_bunkr (bool): Flag to trigger additional checks for bunkr downloads.
        file_name (Optional[str]): Optional file name override.
    """
    url_info = utils.get_url_data(item_url)
    file_name = file_name or url_info["file_name"]
    final_path = os.path.join(download_path, file_name)

    with session.get(item_url, stream=True, timeout=5) as response:
        if response.status_code != 200:
            print(f"\t[-] Error {response.status_code} downloading {file_name}")
            return
        # Check if the server is down for maintenance.
        if response.url == "https://bnkr.b-cdn.net/maintenance.mp4":
            print(f"\t[-] Server maintenance detected for {file_name}")
            return

        try:
            file_size = int(response.headers.get("content-length", -1))
        except (ValueError, TypeError):
            file_size = -1

        with open(final_path, "wb") as f:
            with tqdm(
                total=file_size, unit="iB", unit_scale=True, desc=file_name, leave=False
            ) as progress:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        progress.update(len(chunk))

    # Verify file integrity for bunkr downloads.
    if is_bunkr and file_size > 0:
        downloaded_size = os.stat(final_path).st_size
        if downloaded_size != file_size:
            print(
                f"\t[-] File size mismatch for {file_name}; the file may be corrupted."
            )
            return

    utils.mark_as_downloaded(item_url, download_path)
