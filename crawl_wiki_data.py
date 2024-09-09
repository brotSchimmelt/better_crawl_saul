import argparse
import logging
import os
import time

from src.crawler import WikiCrawler
from src.settings import DOMAINS, WIKIPEDIA_MAIN_CATEGORIES


def parse_arguments() -> argparse.Namespace:
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
    start_time = time.time()

    # logging configuration
    script_name = os.path.basename(__file__).replace(".py", "")
    logging.basicConfig(
        filename=f"./logs/{script_name}.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    args = parse_arguments()
    main(args)

    # run time
    duration = time.time() - start_time
    hours, remainder = divmod(duration, 3600)
    minutes, seconds = divmod(remainder, 60)
    print(f"Crawling finished in {int(hours):02}:{int(minutes):02}:{int(seconds):02}")
