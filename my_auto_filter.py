import argparse
import json
import logging
import os

from src.settings import DOMAINS, WIKIPEDIA_MAIN_CATEGORIES
from src.utils import clean_text, read_data, remove_duplicates


def parse_arguments() -> argparse.Namespace:
    """Simple argument parser."""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--domain",
        type=str,
        help="Specify document domain, please select from: wikipedia or wikinews",
    )
    args = parser.parse_args()

    if args.domain not in DOMAINS:
        raise ValueError(f"Invalid domain: {args.domain} | {DOMAINS}")

    return args


def wiki_merge_all(domain: str) -> None:
    """
    Merge all raw revision files into a structured JSON file per category.

    Args:
        domain (str): The domain to process (e.g., 'wikipedia' or 'wikinews').

    This function reads raw JSON files, filters out unwanted revisions,
    cleans the text, and merges them into consolidated JSON files organized by category.
    """
    tmp_path = f"./data/{domain}/auto"
    os.makedirs(tmp_path, exist_ok=True)

    if domain == "wikipedia":
        categories = WIKIPEDIA_MAIN_CATEGORIES
    else:
        categories = ["all"]

    for category in categories:
        current_dir = f"./data/{domain}/raw/{category}"
        if not os.path.exists(current_dir):
            continue

        print(f"Currently processing {domain} - {category}")

        all_dict = {}
        counter = 0
        files = os.listdir(current_dir)
        for file_name in files:
            if not file_name.endswith(".json"):
                continue

            print(f"filtering {file_name} ...")
            lines = read_data(f"{current_dir}/{file_name}")

            if not isinstance(lines, list):
                logging.info(f"Error reading {file_name}: {lines}")
                logging.info(f"Found type: {type(lines)}")
                continue

            for line in lines:
                before_revision = clean_text(line["parent_content"], domain)
                after_revision = clean_text(line["cur_content"], domain)

                # filter documents which do not have enough edits
                if (
                    "Category:" in line["title"]
                    or "List of " in line["title"]
                    or before_revision == after_revision
                ):
                    continue

                tmp = {
                    "revid": line["revid"],
                    "timestamp": line["timestamp"],
                    "title": line["title"],
                    "before_revision": before_revision,
                    "after_revision": after_revision,
                }

                if line["pageid"] not in all_dict.keys():  # new page
                    all_dict[line["pageid"]] = [tmp]
                    counter += 1
                else:
                    all_dict[line["pageid"]] += [tmp]

        with open(f"{tmp_path}/{domain}_{category}_raw_{counter}.json", "w") as json_file:
            json.dump(all_dict, json_file, indent=2)


def extract_rev_history(domain: str, path: str) -> None:
    """
    Extract and sort revision history of each document into a consolidated JSON file.

    Args:
        domain (str): The domain to process (e.g., 'wikipedia' or 'wikinews').
        path (str): The directory path to save the output JSON file.

    This function reads merged JSON files, removes duplicate revisions, sorts them,
    and writes the revision history for each document to a new JSON file.
    """
    docs = []
    current_dir = f"./data/{domain}/auto"
    files = os.listdir(current_dir)

    with open(f"{path}/raw_{domain}.json", "a") as json_file:
        for file_name in files:
            if not file_name.endswith(".json"):
                continue

            with open(f"{current_dir}/{file_name}", "r") as f:
                all_dict = json.load(f)
            print(file_name)

            counter = 0
            for doc_id, rev_list in all_dict.items():
                if doc_id in docs:
                    continue

                if len(rev_list) > 1:
                    rev_list = remove_duplicates(rev_list)

                for idx, rev in enumerate(rev_list):
                    tmp = {
                        "doc_id": doc_id,
                        "version_depth": idx + 1,
                        "before_revision": rev["before_revision"],
                        "after_revision": rev["after_revision"],
                    }
                    json_file.write(json.dumps(tmp) + "\n")
                    counter += 1
                docs.append(doc_id)


def main(args: argparse.Namespace) -> None:
    wiki_merge_all(args.domain)

    filtered_path = "./data/filtered_revisions"
    os.makedirs(filtered_path, exist_ok=True)

    extract_rev_history(args.domain, filtered_path)


if __name__ == "__main__":
    # logging configuration
    script_name = os.path.basename(__file__).replace(".py", "")
    logging.basicConfig(
        filename=f"./logs/{script_name}.log",
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    args = parse_arguments()
    main(args)
