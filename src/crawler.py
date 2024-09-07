import json
import os
import threading

import mwparserfromhell
import requests

from src.settings import API_URLS, DOMAINS, WIKIPEDIA_CATEGORIES, WIKIPEDIA_MAIN_CATEGORIES
from src.utils import get_time_range


class WikiCrawler:
    def __init__(self, domain: str, main_category: str, years_back: int = 1) -> None:
        if domain not in DOMAINS:
            raise ValueError(f"Invalid domain: {domain}")

        if main_category not in WIKIPEDIA_MAIN_CATEGORIES:
            raise ValueError(f"Invalid main category: {main_category}")

        self.domain = domain
        self.main_category = main_category
        self.years_back = years_back

        self.url = API_URLS[domain]
        self.categories = WIKIPEDIA_CATEGORIES[main_category]

        self.tmp_path = f"./data/{self.domain}/raw/{self.main_category}"
        os.makedirs(self.tmp_path, exist_ok=True)

        self.file_lock = threading.Lock()
        self.session = requests.Session()

        self.start, self.end = get_time_range(self.years_back)

    def get_data(self, gcmcontinue: str, gcmtitle: str):
        if gcmcontinue:
            params = {
                "action": "query",
                "generator": "categorymembers",
                "gcmtitle": gcmtitle,
                "gcmsort": "timestamp",
                "gcmlimit": "100",
                "gcmdir": "desc",
                "gcmcontinue": gcmcontinue,
                "formatversion": "2",
                "format": "json",
            }
        else:
            params = {
                "action": "query",
                "generator": "categorymembers",
                "gcmtitle": gcmtitle,
                "gcmsort": "timestamp",
                "gcmlimit": "100",
                "gcmdir": "desc",
                "gcmstart": self.end,
                "formatversion": "2",
                "format": "json",
            }

        try:
            response = self.session.get(url=self.url, params=params)
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request failed: {e}")
            return [], ""

        try:
            pages = data["query"]["pages"]
        except KeyError:
            pages = []
            print(f"Cannot get data for {gcmtitle}!")

        try:
            gcmcontinue = data["continue"]["gcmcontinue"]
        except KeyError:
            gcmcontinue = ""

        return pages, gcmcontinue

    def get_last_n_revisions(self, pageid: int, n: int = 20):
        response = self.session.get(
            url=self.url,
            params={
                "action": "query",
                "prop": "revisions",
                "pageids": f"{pageid}",
                "rvlimit": f"{n}",
                "formatversion": "2",
                "format": "json",
            },
        )
        data = response.json()
        try:
            revisions = data["query"]["pages"][0]["revisions"]
        except (KeyError, IndexError):
            revisions = []
            print(f"Cannot get revisions for page ID: {pageid}!")
        return revisions

    def parse_revision(self, pages: list, json_file):
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

    def fetch_revision_content(self, revid: int):
        response = self.session.get(
            url=self.url,
            params={
                "action": "query",
                "prop": "revisions",
                "revids": f"{revid}",
                "rvslots": "main",
                "rvprop": "content",
                "formatversion": "2",
                "format": "json",
            },
        )
        data = response.json()
        try:
            content = data["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"]
            return mwparserfromhell.parse(content).strip_code()
        except (KeyError, IndexError):
            print(f"Failed to parse revision content for {revid}")
            return ""

    def write_to_file(self, json_file, data):
        with self.file_lock:
            json_file.write(json.dumps(data) + "\n")

    def process_category(self, category):
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

    def crawl(self):
        threads = []
        for category in self.categories:
            thread = threading.Thread(target=self.process_category, args=(category,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()
        print("Crawling complete.")
