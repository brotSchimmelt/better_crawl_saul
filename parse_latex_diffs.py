import argparse
import json
import logging
import os
import re
import time
from typing import Dict, List, Tuple

from nltk.tokenize import sent_tokenize
from tqdm import tqdm

from src.settings import DOMAINS, URL_PLACEHOLDER
from src.utils import (
    clean_abstract,
    remove_newlines_in_brackets,
    standardize_latexdiff_commands,
    strip_latex_command,
)


def parse_arguments() -> argparse.Namespace:
    """
    Simple argument parser.
    """
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


def parse_latexdiffs(latexdiff_directory: str, domain: str) -> Dict[str, str]:
    """
    Parses LaTeX diff files from a specified directory and extracts relevant information about text
    revisions.

    This function processes all LaTeX diff files in the provided directory, looking for differences
    in text within the abstract sections of the documents. It extracts the original
    ("before revision") and revised ("after revision") text, as well as the type of edit
    (addition, deletion, or replacement) made to the text.

    Args:
        latexdiff_directory (str): The path to the directory containing LaTeX diff `.tex` files.
        domain (str): A string representing the domain or category of the documents being processed
        (e.g., "wikipedia", "wikinews").

    Returns:
        Dict[str, str]: A list of dictionaries, where each dictionary contains the following keys:
            - "doc_id" (str): The document ID extracted from the file name.
            - "revision_depth" (str): The revision depth or number, also extracted from the file
                name.
            - "before_revision" (str): The original text before the edit.
            - "after_revision" (str): The revised text after the edit.
            - "edit_type" (str): The type of edit, either "A" (add), "D" (delete), or "R" (replace).
            - "before_edit" (str): The specific text that was present before the edit.
            - "after_edit" (str): The specific text that replaced or was added during the edit.

    Raises:
        ValueError: If no LaTeX diff files are found in the provided directory.
    """
    diff_files = [f for f in os.listdir(latexdiff_directory) if f.endswith(".tex")]
    logging.info(f"Processing {len(diff_files)} LaTeX diffs from: {latexdiff_directory}")

    if not diff_files:
        raise ValueError(f"No LaTeX diff files found in {latexdiff_directory}")

    skipped_abstracts = 0
    data = []
    for diff_file in tqdm(diff_files, desc=f"Processing {domain}", unit="file"):
        # extract the abstract text from the diff file
        diff_file_path = os.path.join(latexdiff_directory, diff_file)
        abstract = extract_abstract_text(diff_file_path)

        if not abstract:
            logging.error(f"Could not find abstract in {diff_file}")
            continue

        # find the sentence that contains the diff
        diff_sentence = find_diff_sentence(abstract)

        if not diff_sentence:
            skipped_abstracts += 1
            continue

        # extract the two text version and the edit actions
        before_revision, after_revision, edit_actions = parse_edits(diff_sentence)

        # simple sanity checks
        if any(not var for var in [before_revision, after_revision, edit_actions]):
            continue

        if not edit_actions[0]["before"] and not edit_actions[0]["after"]:
            continue

        if len(edit_actions) > 1:
            logging.info(f"Multiple edits found in {diff_file}")
            continue

        # get doc_id and revision_depth from file name
        doc_id, revision_depth = get_revision_depth_doc_id(diff_file)

        tmp_data = {
            "doc_id": doc_id,
            "revision_depth": revision_depth,
            "before_revision": before_revision,
            "after_revision": after_revision,
            "edit_type": edit_actions[0]["type"],
            "before_edit": edit_actions[0]["before"],
            "after_edit": edit_actions[0]["after"],
        }
        data.append(tmp_data)

    print(f"Processed {len(data)} diffs. Skipped {skipped_abstracts}. Kept {len(data)}.")

    return data


def parse_edits(latex_diff_text: str) -> Tuple[str, str, List[Dict]]:
    """
    Parses the LaTeX diff commands to construct the 'before revision' and 'after revision' text.
    Also, determines the type of each edit (Add, Delete, Replace).

    Args:
        latex_diff_text (str): The input LaTeX string containing DIFadd and DIFdel commands.

    Returns:
        Tuple[str, str, List[Dict]]: A tuple containing:
            - before_revision (str): The text before the edit.
            - after_revision (str): The text after the edit.
            - edit_actions (List[Dict]): List of edit actions with type, before, and after text.
    """

    def _process_match(matched: re.Match, action_type: str) -> str:
        """Helper function to process the matched regex for each edit type."""
        if action_type == "R":  # Replace
            before = " ".join(matched.group(1).strip().split())
            after = " ".join(matched.group(2).strip().split())
            edit_actions.append({"type": action_type, "before": before, "after": after})
            return before
        elif action_type == "D":  # Delete
            before = " ".join(matched.group(1).strip().split())
            edit_actions.append({"type": action_type, "before": before, "after": None})
            return before
        elif action_type == "A":  # Add
            after = " ".join(matched.group(1).strip().split())
            edit_actions.append({"type": action_type, "before": None, "after": after})
            return ""
        return ""  # fallback, should never be reached

    # regular expressions to match replace, delete, and add actions
    rgx_replace = r"\\DIFdel\{((?:\\}|[^\}])*)\} *\\DIFadd\{((?:\\}|[^\}])*)\}"
    rgx_delete = r"\\DIFdel\{((?:\\}|[^\}])*)\}"
    rgx_add = r"\\DIFadd\{((?:\\}|[^\}])*)\}"

    edit_actions = []

    before_revision = re.sub(rgx_replace, lambda m: _process_match(m, "R"), latex_diff_text)
    before_revision = re.sub(rgx_delete, lambda m: _process_match(m, "D"), before_revision)
    before_revision = re.sub(rgx_add, lambda m: _process_match(m, "A"), before_revision)

    # normalize the whitespace
    before_revision = " ".join(before_revision.split())

    after_revision = build_after_revision(before_revision, edit_actions)

    return before_revision, after_revision, edit_actions


def build_after_revision(before_revision: str, edit_actions: List[Dict]) -> str:
    """
    Constructs the after_revision text using the edit actions.

    Args:
        before_revision (str): The original text before edits.
        edit_actions (List[Dict]): List of edit actions with type, before, and after text.

    Returns:
        str: The text after the revisions are applied.
    """
    chunks = []
    index = 0

    for action in edit_actions:
        start_pos = before_revision.find(action["before"], index) if action["before"] else index
        if start_pos != -1:
            chunks.append(before_revision[index:start_pos])
            index = start_pos + (len(action["before"]) if action["before"] else 0)
        if action["type"] == "R":
            chunks.append(action["after"])
        elif action["type"] == "A":
            chunks.append(action["after"])

    if index < len(before_revision):
        chunks.append(before_revision[index:])

    after_revision = " ".join("".join(chunks).split())
    return after_revision


def find_diff_sentence(abstract: str) -> str:
    """
    Searches through the sentences of the abstract to find the one containing LaTeX diff commands.

    Args:
        abstract (str): The abstract text to search through for diff commands.

    Returns:
        str: The sentence containing the LaTeX diff commands ("DIFdel" or "DIFadd").
        If no diff commands are found, or the sentence contains unwanted text like "Category:" or
        "List of", returns None.
    """
    for s in sent_tokenize(abstract):
        s = s.strip()

        if "DIFdel" in s or "DIFadd" in s:
            if "Category:" in s or "List of" in s:
                return None
            else:
                return s

            return s

    return None


def extract_abstract_text(diff_file_path: str) -> str:
    """
    Extracts and cleans the abstract section from a LaTeX diff file.

    Args:
        diff_file_path (str): The file path to the LaTeX diff file containing the abstract.

    Returns:
        str: The cleaned abstract text with LaTeX diff commands standardized and unnecessary
            elements removed.
        If the abstract cannot be extracted, returns None.
    """
    with open(diff_file_path, "r") as f:
        raw_text = f.read()

        rgx_abstract = r"\\begin\{abstract\}(.+)\\end\{abstract\}"
        abstract_match = re.search(rgx_abstract, raw_text, re.DOTALL)

        if abstract_match:
            abstract = abstract_match.group(1)
        else:
            return None

    abstract = clean_abstract(abstract, URL_PLACEHOLDER)
    abstract = remove_newlines_in_brackets(abstract)
    abstract = standardize_latexdiff_commands(abstract)
    return strip_latex_command(abstract)


def get_revision_depth_doc_id(latex_diff_path: str) -> Tuple[str, str]:
    """
    Extracts the document ID and revision depth from the LaTeX diff file name.

    Args:
        latex_diff_path (str): The file path to the LaTeX diff file, which includes the revision
        information in its name.

    Returns:
        Tuple[str, str]: A tuple containing:
            - doc_id (str): The document ID extracted from the file name.
            - revision_depth (str): Revision depth (version number) extracted from the file name.
    """
    rgx_basename = r"(.+)_diff_v(\d+)v(\d+)\.tex"
    basename = os.path.basename(latex_diff_path)
    basename_match = re.match(rgx_basename, basename)
    assert basename_match
    doc_id = basename_match.group(1)
    revision_depth = basename_match.group(2)

    return doc_id, revision_depth


def write_data_to_file(data: List[Dict[str, str]], output_path: str) -> None:
    """
    Writes the parsed data to a JSON file.

    Args:
        data (List[Dict[str, str]]): A list of dictionaries containing the parsed LaTeX diff data.
        output_path (str): The file path where the data should be written.
    """
    if not data:
        logging.error("No data to write to file.")
        return

    with open(output_path, "w") as json_file:
        json.dump(data, json_file, indent=2)


def main(args: argparse.Namespace) -> None:
    os.makedirs("./data/extracted_revisions", exist_ok=True)

    # extract revisions from latexdiff files
    latexdiff_directory = f"./data/extracted_revisions/latexdiff_{args.domain}/"
    data = parse_latexdiffs(latexdiff_directory, args.domain)

    # write data to file
    output_path = f"./data/extracted_revisions/{args.domain}_revisions.json"
    write_data_to_file(data, output_path)


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
    print(f"Script finished in {int(hours):02}:{int(minutes):02}:{int(seconds):02}")
