import argparse

from src.crawler import WikiCrawler

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain",
        default="wikipedia",
        type=str,
        help="Specify document domain, please select from: wikipedia, wikinews",
    )
    parser.add_argument(
        "--main_category",
        default="philosophy",
        type=str,
        help="Specify main category of documents under each domain",
    )
    parser.add_argument(
        "--years_back",
        default=1,
        type=int,
        help="Specify the number of years to go back from the current date",
    )
    args = parser.parse_args()

    crawler = WikiCrawler(args.domain, args.main_category, args.years_back)
    crawler.crawl()
