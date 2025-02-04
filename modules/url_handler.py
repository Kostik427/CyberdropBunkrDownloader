"""
url_handler.py
==============

Implements the Strategy design pattern for resolving the real download URL
depending on the source (e.g., Bunkr or Cyberdrop).

Classes:
    - URLHandler: Base class/interface for URL resolution.
    - BunkrURLHandler: Resolves download URLs for bunkr pages.
    - CyberdropURLHandler: Resolves download URLs for Cyberdrop pages.
    - URLHandlerFactory: Provides the appropriate URL handler based on input.

Functions:
    - get_url_handler(is_bunkr: bool) -> URLHandler: Factory function.
"""

import json
from typing import Optional, Dict, Any
import requests
from bs4 import BeautifulSoup
from modules import utils


class URLHandler:
    """
    Base class for URL resolution.
    """

    def get_real_download_url(
        self, session: requests.Session, cdn_list: Optional[list], url: str
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve the real download URL for the given page.

        Args:
            session (requests.Session): The session for HTTP requests.
            cdn_list (Optional[list]): List of CDN hosts.
            url (str): The page URL to resolve.

        Returns:
            Optional[Dict[str, Any]]: Dictionary with the real URL and metadata,
                                      or None if resolution fails.
        """
        raise NotImplementedError("Subclasses must implement this method.")


class BunkrURLHandler(URLHandler):
    """
    URL handler for bunkr pages.
    """

    def get_real_download_url(
        self, session: requests.Session, cdn_list: Optional[list], url: str
    ) -> Optional[Dict[str, Any]]:
        # Ensure the URL is complete.
        if not url.startswith("https"):
            url = f"https://bunkr.sk{url}"

        response = session.get(url)
        if response.status_code != 200:
            print(f"\t[-] HTTP error {response.status_code} while resolving {url}")
            return None

        soup = BeautifulSoup(response.content, "html.parser")
        # Try various DOM elements to extract the media URL.
        for tag, attr in [("source", "src"), ("media-player", "src"), ("img", "src")]:
            element = soup.find(tag, {"class": "max-h-full"} if tag == "img" else None)
            if element and element.get(attr):
                return {"url": element[attr], "size": -1}

        # If a specific link is required, try using the CDN helper.
        link_dom = soup.find("h1", {"class": "truncate"})
        if link_dom:
            resolved_url = utils.get_cdn_file_url(session, cdn_list, url)
            return {"url": resolved_url, "size": -1} if resolved_url else None

        return None


class CyberdropURLHandler(URLHandler):
    """
    URL handler for Cyberdrop pages.
    """

    def get_real_download_url(
        self, session: requests.Session, cdn_list: Optional[list], url: str
    ) -> Optional[Dict[str, Any]]:
        # Modify the URL to point to the API endpoint.
        api_url = url.replace("/f/", "/api/f/")
        response = session.get(api_url)
        if response.status_code != 200:
            print(f"\t[-] HTTP error {response.status_code} while resolving {url}")
            return None

        try:
            item_data = json.loads(response.content)
            return {"url": item_data["url"], "size": -1, "name": item_data.get("name")}
        except json.JSONDecodeError as e:
            print(f"\t[-] JSON decoding error: {e}")
            return None


class URLHandlerFactory:
    """
    Factory class to obtain the correct URL handler.
    """

    @staticmethod
    def get_url_handler(is_bunkr: bool) -> URLHandler:
        """
        Return an instance of URLHandler based on the provided flag.

        Args:
            is_bunkr (bool): True if the page is from bunkr, else Cyberdrop.

        Returns:
            URLHandler: The appropriate URL handler instance.
        """
        if is_bunkr:
            return BunkrURLHandler()
        else:
            return CyberdropURLHandler()
