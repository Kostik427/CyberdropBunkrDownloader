"""
utils.py
========

Utility functions for handling file paths, file I/O, and URL parsing.

Functions:
    - get_url_data(url: str) -> dict: Parse a URL and return file details.
    - remove_illegal_chars(string: str) -> str: Remove invalid file name characters.
    - get_and_prepare_download_path(custom_path: Optional[str], album_name: str) -> str:
          Prepare and return the download directory path.
    - write_url_to_list(item_url: str, download_path: str) -> None: Append URL to a file.
    - get_already_downloaded_url(download_path: str) -> list: Read downloaded URLs.
    - mark_as_downloaded(item_url: str, download_path: str) -> None: Log a downloaded URL.
    - get_cdn_file_url(...): Attempt to build a valid CDN URL.
"""

import os
import re
from typing import Optional, Dict
from urllib.parse import urlparse
import requests
import threading

# A global lock for thread-safe file I/O.
file_lock = threading.Lock()


def get_url_data(url: str) -> Dict[str, str]:
    """
    Parse the URL and return a dictionary with file name, extension, and hostname.

    Args:
        url (str): The URL to parse.

    Returns:
        dict: Contains keys 'file_name', 'extension', and 'hostname'.
    """
    parsed_url = urlparse(url)
    file_name = os.path.basename(parsed_url.path)
    return {
        "file_name": file_name,
        "extension": os.path.splitext(file_name)[1],
        "hostname": parsed_url.hostname or "",
    }


def remove_illegal_chars(string: str) -> str:
    """
    Remove characters that are not allowed in file/directory names.

    Args:
        string (str): Input string.

    Returns:
        str: Cleaned string with illegal characters replaced.
    """
    return re.sub(r'[<>:"/\\|?*\']|[\0-\31]', "-", string).strip()


def get_and_prepare_download_path(
    custom_path: Optional[str], album_name: Optional[str]
) -> str:
    """
    Prepare the download directory and the tracking file for already downloaded URLs.

    Args:
        custom_path (Optional[str]): Custom base directory (or None).
        album_name (Optional[str]): The album name to create a subdirectory.

    Returns:
        str: The final download path.
    """
    base_path = custom_path if custom_path else "downloads"
    final_path = os.path.join(base_path, album_name) if album_name else base_path
    final_path = final_path.replace("\n", "")

    if not os.path.isdir(final_path):
        os.makedirs(final_path)

    # Initialize the already_downloaded.txt file if it doesn't exist.
    already_downloaded_path = os.path.join(final_path, "already_downloaded.txt")
    if not os.path.isfile(already_downloaded_path):
        with file_lock:
            with open(already_downloaded_path, "w", encoding="utf-8"):
                pass

    return final_path


def write_url_to_list(item_url: str, download_path: str) -> None:
    """
    Append the URL to the url_list.txt file in the download path.

    Args:
        item_url (str): URL to write.
        download_path (str): Path to the download folder.
    """
    list_path = os.path.join(download_path, "url_list.txt")
    with file_lock:
        with open(list_path, "a", encoding="utf-8") as f:
            f.write(f"{item_url}\n")


def get_already_downloaded_url(download_path: str) -> list:
    """
    Read the already_downloaded.txt file and return a list of URLs.

    Args:
        download_path (str): Download directory path.

    Returns:
        list: List of URLs that have been downloaded.
    """
    file_path = os.path.join(download_path, "already_downloaded.txt")
    if not os.path.isfile(file_path):
        return []

    with file_lock:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read().splitlines()


def mark_as_downloaded(item_url: str, download_path: str) -> None:
    """
    Append a successfully downloaded URL to the already_downloaded.txt file.

    Args:
        item_url (str): The URL that was downloaded.
        download_path (str): The directory where downloads are saved.
    """
    file_path = os.path.join(download_path, "already_downloaded.txt")
    with file_lock:
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(f"{item_url}\n")


def get_cdn_file_url(
    session: requests.Session,
    cdn_list: Optional[list],
    gallery_url: str,
    file_name: Optional[str] = None,
) -> Optional[str]:
    """
    Attempt to build a valid CDN URL using the provided CDN host list.

    Args:
        session (requests.Session): Session to use for the request.
        cdn_list (Optional[list]): List of CDN hosts.
        gallery_url (str): The original gallery URL.
        file_name (Optional[str]): Specific file name (if any).

    Returns:
        Optional[str]: A valid CDN URL if found, else None.
    """
    if not cdn_list:
        print(f"\t[-] CDN list is empty, unable to resolve {gallery_url}")
        return None

    for cdn in cdn_list:
        if file_name is None:
            pos = gallery_url.find("/d/")
            if pos == -1:
                print(f"\t[-] Expected '/d/' in URL: {gallery_url}")
                return None
            url_to_test = f"https://{cdn}/{gallery_url[pos+3:]}"
        else:
            url_to_test = f"https://{cdn}/{file_name}"

        try:
            response = session.get(url_to_test, timeout=20)
        except requests.RequestException:
            continue

        if response.status_code == 200:
            return url_to_test
        elif response.status_code == 404:
            continue
        elif response.status_code == 403:
            print(f"\t[-] Request blocked for {gallery_url}")
            return None
        else:
            print(f"\t[-] HTTP Error {response.status_code} for {gallery_url}")
            return None
    return None
