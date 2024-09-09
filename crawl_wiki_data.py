import argparse

from src.crawler import WikiCrawler
from src.settings import DOMAINS, WIKIPEDIA_MAIN_CATEGORIES


def parse_argument() -> argparse.Namespace:
    """
    Simple argument parser for the script.
    """
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain",
        default="wikipedia",
        type=str,
        help="Specify document domain, please select from: wikipedia, wikinews",
    )
    parser.add_argument(
        "--main_category",
        type=str,
        help="Specify main category. For wikinews use 'all'.",
    )
    parser.add_argument(
        "--years_back",
        default=1,
        type=int,
        help="Specify the number of years to go back from the current date",
    )
    args = parser.parse_args()

    if args.domain not in DOMAINS:
        raise ValueError(f"Invalid domain: {args.domain} | {DOMAINS}")

    # check if main category is aligns with settings.py
    if args.domain == "wikipedia":
        if args.main_category not in WIKIPEDIA_MAIN_CATEGORIES:
            raise ValueError(f"Invalid main category: {args.main_category}")
    elif args.domain == "wikinews":
        args.main_category = "all"

    return args


def main(args: argparse.Namespace) -> None:
    crawler = WikiCrawler(args.domain, args.main_category, args.years_back)
    crawler.crawl()


if __name__ == "__main__":
    args = parse_argument()
    main(args)
