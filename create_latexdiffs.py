import argparse
import json
import logging
import os
import time

from tqdm import tqdm

from src.settings import DOMAINS
from src.utils import clean_text


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


def write_to_latex(tmp_path: str, content: str, file_name: str) -> str:
    """
    Write a given content to a LaTeX file format.

    Args:
        tmp_path (str): Path to the temporary directory.
        content (str): LaTeX content to be written to the file.
        file_name (str): Name of the output file without extension.

    Returns:
        str: Full path to the created LaTeX file.
    """
    file_path = os.path.join(tmp_path, f"{file_name}.tex")
    try:
        with open(file_path, "w") as f:
            f.write("\\documentclass{article}\n")
            f.write("\\begin{document}\n")
            f.write("\\begin{abstract}\n")
            f.write(content)
            f.write("\\end{abstract}\n")
            f.write("\\end{document}\n")
    except Exception as e:
        logging.error(f"Error writing to LaTeX file: {e}")
    return file_path


def generate_latex_diff(
    doc_id: str, ver_id: int, before_revision: str, after_revision: str, tmp_path: str
) -> None:
    """
    Generate a LaTeX diff file between two revisions using latexdiff.

    Args:
        doc_id (str): Document ID.
        ver_id (int): Version ID for the current revision.
        before_revision (str): The content of the previous revision.
        after_revision (str): The content of the current revision.
        tmp_path (str): Path to the temporary directory.
    """
    os.makedirs(tmp_path, exist_ok=True)

    preprint_v1 = f"{doc_id}v{ver_id}"
    preprint_v2 = f"{doc_id}v{ver_id+1}"
    source_file = write_to_latex(tmp_path, before_revision, preprint_v1)
    target_file = write_to_latex(tmp_path, after_revision, preprint_v2)

    diff_file_path = os.path.join(tmp_path, f"{doc_id}_diff_v{ver_id}v{ver_id+1}.tex")
    latexdiff_command = f"latexdiff --ignore-warnings --math-markup=0 {source_file} {target_file} > {diff_file_path}"  # noqa: E501

    try:
        os.system(latexdiff_command)
    except Exception as e:
        logging.error(f"Error generating diff: {doc_id} -> {e}")

    # clean up non-diff files to save space
    os.remove(source_file)
    os.remove(target_file)


def create_diffs(directory: str, domain: str) -> None:
    """
    Parse diffs for all files in a specified directory.

    Args:
        directory (str): Path to the directory containing revision files.
        domain (str): Domain name (e.g., 'wikipedia' or 'wikinews').
    """
    # path to save the temporary latexdiff files
    latexdiff_path = os.path.join("./data/extracted_revisions", f"latexdiff_{domain}")
    os.makedirs(latexdiff_path, exist_ok=True)

    files = [f for f in os.listdir(directory) if domain in f and f.endswith(".json")]

    for file_name in files:
        logging.info(f"Processing file: {file_name}")

        with open(os.path.join(directory, file_name), "r") as f:
            all_docs = f.read().strip().split("\n")

        for line in tqdm(all_docs, desc=f"Processing {file_name}", unit="doc"):
            line_data = json.loads(line)
            doc_id = line_data["doc_id"]
            version_depth = line_data["version_depth"]
            before_revision = clean_text(line_data["before_revision"], domain)
            after_revision = clean_text(line_data["after_revision"], domain)

            # generate latexdiff files for every single revision in the merged data
            generate_latex_diff(
                doc_id, version_depth, before_revision, after_revision, latexdiff_path
            )  # store them to latexdiff_path


def main(args: argparse.Namespace) -> None:
    create_diffs(directory=f"./data/{args.domain}/merged", domain=args.domain)


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
