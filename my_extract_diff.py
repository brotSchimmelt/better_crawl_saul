import argparse
import json
import logging
import os
import re
import time

import numpy as np
import pylatexenc
from nltk.tokenize import word_tokenize
from pylatexenc.latexwalker import LatexWalker
from tqdm import tqdm

from src.settings import DOMAINS, WIKIPEDIA_MAIN_CATEGORIES
from src.utils import clean_text, clean_unused


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
    parser.add_argument(
        "--main_category",
        type=str,
        help="Specify main category. For wikinews use 'all'.",
    )
    args = parser.parse_args()

    if args.domain not in DOMAINS:
        raise ValueError(f"Invalid domain: {args.domain} | {DOMAINS}")

    # check if main category is aligns with settings.py
    if args.main_category is None:
        if args.domain == "wikipedia":
            if args.main_category not in WIKIPEDIA_MAIN_CATEGORIES:
                raise ValueError(f"Invalid main category: {args.main_category}")
        elif args.domain == "wikinews":
            args.main_category = "all"

    return args


def remove_empty(edit_list):
    """
    Remove empty strings from a list.

    Args:
        edit_list (list): List from which to remove empty strings.

    Returns:
        list: A list with all empty strings removed.
    """
    return [item for item in edit_list if item]


def write_to_latex(tmp_path, content, file_name):
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


def generate_latex_diff(doc_id, ver_id, before_revision, after_revision, tmp_path):
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
    latexdiff_command = f"latexdiff --ignore-warnings --math-markup=0 {source_file} {target_file} > {diff_file_path}"

    try:
        os.system(latexdiff_command)
    except Exception as e:
        logging.error(f"Error generating diff: {doc_id} -> {e}")

    # clean up non-diff files to save space
    os.remove(source_file)
    os.remove(target_file)


def extract_diffs_from_latex(file_path):
    """
    Extract meaningful diffs from a LaTeX diff output file.

    Args:
        file_path (str): Path to the LaTeX diff file.

    Returns:
        str: Extracted abstract containing diffs.
    """
    with open(file_path, "r") as f:
        latex = f.read()
    search_obj = re.search(r"begin{abstract}", latex)
    sid = search_obj.end() if search_obj else 0
    abstract = latex[sid:].strip("[ \n]")
    abstract = re.sub(r"\$", "MATH", abstract)
    abstract = re.sub(r"\\newcite{.*}", "CITATION", abstract)

    paras = abstract.split("\n\n")
    return "\nNEW_PARAGRAPH\n".join(para for para in paras if "DIFdel" in para or "DIFadd" in para)


def extract_raw_text(diff_out, mode="DIFdel"):
    """
    Extract raw text content marked by DIFadd or DIFdel tags from the diff output.

    Args:
        diff_out (list): List containing the diff output.
        mode (str): Mode to extract ('DIFdel' or 'DIFadd').

    Returns:
        str: Extracted raw text based on the specified mode.
    """
    abstract = []
    pos_arr = np.zeros(len(diff_out))

    if not diff_out:
        return ""

    for i, diff in enumerate(diff_out):
        if diff in ["DIFdel", "DIFadd"]:
            if i + 1 < len(diff_out):  # ensure i+1 is within bounds
                if diff == mode:
                    abstract.append(diff_out[i + 1])
                    pos_arr[i + 1] = 1
                else:
                    pos_arr[i + 1] = -1
        elif pos_arr[i] == 0:
            abstract.append(diff)

    return " ".join(abstract)


def parse_diffs(ID, ver_id, tmp_path):
    """
    Parse the diffs from a LaTeX diff output file and extract information.

    Args:
        ID (str): Document ID.
        ver_id (int): Version ID for the current revision.
        tmp_path (str): Path to the temporary directory.

    Returns:
        dict: Parsed diff data including raw text and lists of additions and deletions.
    """
    diff_file_path = os.path.join(tmp_path, f"{ID}_diff_v{ver_id}v{ver_id+1}.tex")
    diff_abs = extract_diffs_from_latex(diff_file_path)
    nodes, pos, len_ = LatexWalker(diff_abs).get_latex_nodes(pos=0)

    all_nodes = []
    for i, node in enumerate(nodes):
        if node.isNodeType(pylatexenc.latexwalker.LatexGroupNode):
            prev_node = nodes[i - 1]
            if prev_node.isNodeType(
                pylatexenc.latexwalker.LatexMacroNode
            ) and prev_node.macroname in ["DIFdel", "DIFadd"]:
                for j, char_node in enumerate(node.nodelist):
                    if char_node.isNodeType(pylatexenc.latexwalker.LatexCharsNode):
                        all_nodes += [prev_node, char_node]
                    elif char_node.isNodeType(pylatexenc.latexwalker.LatexGroupNode):
                        for k, cchar_node in enumerate(char_node.nodelist):
                            if cchar_node.isNodeType(pylatexenc.latexwalker.LatexCharsNode):
                                prev_char_node = char_node.nodelist[k - 1]
                                if prev_char_node.isNodeType(
                                    pylatexenc.latexwalker.LatexMacroNode
                                ) and prev_char_node.macroname in ["DIFdel", "DIFadd"]:
                                    all_nodes += [prev_char_node, cchar_node]
                                else:
                                    all_nodes += [prev_node, cchar_node]
        if node.isNodeType(pylatexenc.latexwalker.LatexCharsNode):
            all_nodes += [node]

    diff_out, delete_list, add_list = [], [], []
    for i, node in enumerate(all_nodes):
        if node.isNodeType(pylatexenc.latexwalker.LatexCharsNode):
            chars = node.chars.replace("MATH", "").replace("DIFdelbegin", "")
            char_str = " ".join(word_tokenize(chars))
            if char_str:
                diff_out.append(char_str.replace("NEW_PARAGRAPH", "\n**NEW_PARAGRAPH**\n"))
        elif node.isNodeType(pylatexenc.latexwalker.LatexMacroNode):
            if node.macroname == "DIFdel":
                diff_out.append(node.macroname)
                chars = all_nodes[i + 1].chars.replace("MATH", "").replace("DIFdelbegin", "")
                delete_list.append(clean_unused(" ".join(word_tokenize(chars))))
            elif node.macroname == "DIFadd":
                diff_out.append(node.macroname)
                chars = all_nodes[i + 1].chars.replace("MATH", "").replace("DIFdelbegin", "")
                add_list.append(clean_unused(" ".join(word_tokenize(chars))))

    delete_list = remove_empty(delete_list)
    add_list = remove_empty(add_list)

    source_abs = extract_raw_text(diff_out, mode="DIFdel")
    target_abs = extract_raw_text(diff_out, mode="DIFadd")

    if not diff_out:
        return {}

    return {
        "before_raw_txt": source_abs,
        "after_raw_txt": target_abs,
        "diff_out": diff_out,
        "delete_list": delete_list,
        "add_list": add_list,
    }


def parse_diff(directory, domain):
    """
    Parse diffs for all files in a specified directory.

    Args:
        directory (str): Path to the directory containing revision files.
        domain (str): Domain name (e.g., 'wikipedia' or 'wikinews').
    """
    tmp_path = os.path.join(directory, f"tmp_{domain}")
    os.makedirs(tmp_path, exist_ok=True)

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

            generate_latex_diff(doc_id, version_depth, before_revision, after_revision, tmp_path)
            parsed_data = parse_diffs(doc_id, version_depth, tmp_path)


def main(args: argparse.Namespace) -> None:
    parse_diff(directory="./data/filtered_revisions", domain=args.domain)


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
