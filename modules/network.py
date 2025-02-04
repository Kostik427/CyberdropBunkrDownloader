"""
network.py
==========

Handles network-related functionality such as creating a configured session
and retrieving the list of CDN hosts.

Functions:
    - create_session(): Returns a configured requests.Session.
    - get_cdn_list(session): Retrieves a list of CDN hosts from the status page.
"""

from typing import List, Optional
import requests
from bs4 import BeautifulSoup


def create_session() -> requests.Session:
    """
    Create and return a requests.Session with preset headers.

    Returns:
        requests.Session: A session with custom headers.
    """
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://bunkr.sk/",
        }
    )
    return session


def get_cdn_list(session: requests.Session) -> Optional[List[str]]:
    """
    Retrieve and parse the CDN list from the bunkr status page.

    Args:
        session (requests.Session): The session to use for the GET request.

    Returns:
        Optional[List[str]]: A list of CDN host strings if successful, otherwise None.
    """
    url = "https://status.bunkr.ru/"
    response = session.get(url)
    if response.status_code != 200:
        print(f"[-] HTTP Error {response.status_code} while getting CDN list")
        return None

    cdn_list = []
    soup = BeautifulSoup(response.content, "html.parser")
    cdn_elements = soup.find_all("p", {"class": "flex-1"})
    if cdn_elements:
        # Skip the first few non-CDN items and pick valid CDN names.
        for i, cdn in enumerate(cdn_elements[1:], start=1):
            if i > 4:
                cdn_list.append(f"{cdn.text.lower()}.bunkr.ru")
    return cdn_list
