import json
import logging
import os
import random
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

import mwparserfromhell
import requests

from src.settings import API_URLS, DOMAINS, WIKIPEDIA_CATEGORIES, WIKIPEDIA_MAIN_CATEGORIES
from src.utils import get_time_range


class WikiCrawler:
    def __init__(self, domain: str, main_category: str, years_back: int = 1) -> None:
        """
        Initializes the WikiCrawler instance with the given domain and category.

        Args:
            domain (str): The Wikipedia domain (e.g., "en", "fr").
            main_category (str): The main category to crawl (e.g., "History").
            years_back (int, optional): How many years back to retrieve revisions. Defaults to 1.

        Raises:
            ValueError: If the domain or main category is invalid.
        """
        if domain not in DOMAINS:
            raise ValueError(f"Invalid domain: {domain}")

        if domain == "wikinews":
            self.categories = ["Published", "Original_reporting"]
        else:
            if main_category not in WIKIPEDIA_MAIN_CATEGORIES:
                raise ValueError(f"Invalid main category: {main_category}")
            self.categories = WIKIPEDIA_CATEGORIES[main_category]

        self.domain = domain
        self.main_category = main_category
        self.years_back = years_back

        self.url = API_URLS[domain]

        self.tmp_path = f"./data/{self.domain}/raw/{self.main_category}"
        os.makedirs(self.tmp_path, exist_ok=True)

        self.file_lock = threading.Lock()
        self.session = requests.Session()

        self.start, self.end = get_time_range(self.years_back)

    def get_data(self, gcmcontinue: str, gcmtitle: str) -> Tuple[list, str]:
        """
        Retrieves pages for the given category title from Wikipedia.

        Args:
            gcmcontinue (str): Continuation parameter for paginated API requests.
            gcmtitle (str): The category title to fetch data for.

        Returns:
            Tuple[list, str]: A tuple containing the list of pages and the continuation token.
        """
        params = {
            "action": "query",
            "generator": "categorymembers",
            "gcmtitle": gcmtitle,
            "gcmlimit": "100",
            "formatversion": "2",
            "format": "json",
        }

        if gcmcontinue:
            params["gcmcontinue"] = gcmcontinue
        else:
            params["gcmstart"] = self.end

        if self.domain == "wikipedia":
            params["gcmsort"] = "timestamp"
            params["gcmdir"] = "desc"

        response = self.retry_request(self.url, params)
        if not response:
            return [], ""

        data = response.json()
        pages = data.get("query", {}).get("pages", [])
        gcmcontinue = data.get("continue", {}).get("gcmcontinue", "")

        return pages, gcmcontinue

    def get_last_n_revisions(self, pageid: int, n: int = 20) -> list:
        """
        Retrieves the last n revisions of a given page ID.

        Args:
            pageid (int): The ID of the Wikipedia page.
            n (int, optional): The number of revisions to retrieve. Defaults to 20.

        Returns:
            list: A list of revisions for the specified page.
        """
        params = {
            "action": "query",
            "prop": "revisions",
            "pageids": f"{pageid}",
            "rvlimit": f"{n}",
            "formatversion": "2",
            "format": "json",
        }

        response = self.retry_request(self.url, params)
        if not response:
            return []

        data = response.json()
        revisions = data.get("query", {}).get("pages", [])[0].get("revisions", [])

        return revisions

    def parse_revision(self, pages: list, json_file) -> list:
        """
        Parses the revision content for a list of pages and writes the data to a file.

        Args:
            pages (list): A list of pages to process.
            json_file (file object): The file to write the revisions data into.

        Returns:
            list: A list of revisions processed and saved to the file.
        """
        out = []
        for page in pages:
            pageid = page["pageid"]
            title = page["title"]
            revisions = self.get_last_n_revisions(pageid)

            for rev in revisions:
                if rev.get("minor"):
                    continue

                rev["pageid"] = pageid
                rev["title"] = title
                revid = rev["revid"]
                parentid = rev.get("parentid")

                current_content = self.fetch_revision_content(revid)
                parent_content = self.fetch_revision_content(parentid) if parentid else ""

                if not current_content or not parent_content:
                    continue

                rev["cur_content"] = current_content
                rev["parent_content"] = parent_content

                self.write_to_file(json_file, rev)
                out.append(rev)
        return out

    def fetch_revision_content(self, revid: int) -> str:
        params = {
            "action": "query",
            "prop": "revisions",
            "revids": f"{revid}",
            "rvslots": "main",
            "rvprop": "content",
            "formatversion": "2",
            "format": "json",
        }

        response = self.retry_request(self.url, params)
        if not response:
            return ""

        try:
            data = response.json()
            content = data["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
            return mwparserfromhell.parse(content).strip_code()
        except (KeyError, IndexError, ValueError) as e:
            logging.info(f"Failed to parse revision content for {revid}: {e}")
            return ""

    def write_to_file(self, json_file, data: dict) -> None:
        """
        Writes a dictionary as a JSON line to the provided file.

        Args:
            json_file (file object): The file to write the data into.
            data (dict): The data to write as a JSON line.
        """
        with self.file_lock:
            json_file.write(json.dumps(data) + "\n")

    def process_category(self, category: str) -> None:
        """
        Processes a specific Wikipedia category and fetches the revision data.

        Args:
            category (str): The category to process.
        """
        gcmtitle = f"Category:{category}"
        print(f"Processing {gcmtitle}")

        gcmcontinue = ""
        file_path = os.path.join(self.tmp_path, f"raw_revisions_{category}.json")

        with open(file_path, "a") as json_file:
            while True:
                pages, gcmcontinue = self.get_data(gcmcontinue, gcmtitle)
                if not pages:
                    print(f"No pages returned for {gcmtitle}. Ending this category.")
                    break
                out = self.parse_revision(pages, json_file)
                print(f"Write {len(out)} data into raw_revisions_{category}.json")
                if not gcmcontinue:
                    print(f"No more pages to continue for {gcmtitle}.")
                    break

    def crawl(self) -> None:
        """
        Starts the crawling process for all categories and retrieves Wikipedia revision data.
        Limits concurrency to 4 threads.
        """
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [
                executor.submit(self.process_category, category) for category in self.categories
            ]

            for future in as_completed(futures):
                try:
                    future.result()  # This will raise any exceptions caught in the thread
                except Exception as e:
                    print(f"Error occurred: {e}")

        print("Crawling complete.")

    def retry_request(self, url, params, retries=5, backoff_factor=0.5) -> requests.Response:
        """
        A helper function to make HTTP requests with retries and exponential backoff.
        """
        for attempt in range(retries):
            try:
                response = self.session.get(url=url, params=params)
                response.raise_for_status()
                return response
            except requests.exceptions.HTTPError as e:
                if response.status_code == 429:  # Too Many Requests (rate-limited)
                    sleep_time = backoff_factor * (2**attempt) + random.uniform(0, 1)
                    print(f"Rate limited! Sleeping for {sleep_time:.2f} seconds before retrying...")
                    time.sleep(sleep_time)
                else:
                    print(f"HTTP request failed: {e}")
                    return None
            except requests.exceptions.RequestException as e:
                print(f"HTTP request failed: {e}")
                return None
        return None
