import json
import logging
import os
import re
import string
from datetime import datetime
from typing import List, Tuple


def get_time_range(years_back: int = 1) -> Tuple[str, str]:
    """
    Calculate the start and end time range in ISO 8601 format based on the current date.

    Args:
        years_back (int): The number of years to go back from the current date.

    Returns:
        Tuple[str, str]: A tuple containing the start and end date-time strings in ISO 8601 format.
    """
    my_date = datetime.now()
    end = my_date.isoformat()
    start_date = my_date.replace(year=my_date.year - years_back)
    start = start_date.isoformat()
    return start, end


def read_data(file_path: str) -> List[dict]:
    """
    Reads data from a JSON file where each line is a separate JSON object.

    Args:
        file_path (str): The path to the JSON file to read.

    Returns:
        List[dict]: List of parsed JSON objects or an empty list if the file is empty or an error
        occurs.
    """
    lines: List[dict] = []
    try:
        if os.path.getsize(file_path) == 0:
            logging.info(f"File {file_path} is empty.")
            return lines

        with open(file_path, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        lines.append(json.loads(line))
                    except json.JSONDecodeError as e:
                        logging.error(f"JSON decoding error in {file_path}: {e}")
                        continue
    except FileNotFoundError:
        logging.error(f"File {file_path} not found.")
    except Exception as e:
        logging.error(f"An error occurred while reading {file_path}: {e}")

    return lines


def clean_unused(text: str) -> str:
    """
    Removes punctuation from the input text and strips leading/trailing whitespace.

    Args:
        text (str): The input text to clean.

    Returns:
        str: The cleaned text without punctuation and extra whitespace.
    """
    text_clean = text.translate(str.maketrans("", "", string.punctuation))
    return text_clean.strip()


def remove_duplicates(input_list: List[dict]) -> List[dict]:
    """
    Removes duplicate dictionaries from a list of dictionaries, sorting by the "timestamp" key.

    Args:
        input_list (List[dict]): List of dictionaries containing the data.

    Returns:
        List[dict]: A list with duplicates removed and sorted by timestamp.
    """
    input_list.sort(key=lambda x: x["timestamp"])
    seen = set()
    new_l = []
    for d in input_list:
        t = tuple(d.items())
        if t not in seen:
            seen.add(t)
            new_l.append(d)
    return new_l


def clean_text(text: str, domain: str) -> str:
    """
    Cleans and removes specific text patterns depending on the domain (e.g., Wikipedia or Wikinews).

    Args:
        text (str): The input text to clean.
        domain (str): The domain (e.g., "wikipedia" or "wikinews") for which cleaning is applied.

    Returns:
        str: The cleaned text with specific patterns removed.
    """
    try:
        if domain == "wikipedia":
            eid = re.search("\n See also", text).start()
        if domain == "wikinews":
            eid = re.search("Sources", text).start()
    except Exception:
        eid = -1
    text = text[0:eid].strip("[ \n]")
    text = text.replace("thumb|", "")
    text = re.sub(r"right\|+[\d\.]+px\|", "", text)
    text = re.sub(r"left\|+[\d\.]+px\|", "", text)
    text = re.sub(r"upright=+[\d\.]\|", "", text)
    text = text.replace("left|", "")
    text = text.replace("right|", "")
    text = text.replace("https : //", "https://")
    text = text.replace("http : //", "https://")
    text = re.sub("<a.*?>|</a>", "", text, flags=re.MULTILINE)  # remove <a href=''></a>
    text = re.sub(r"\S*https?:\S*", "URL", text)  # replace https://xxx.com with URL
    return text.strip("\n").strip()


def clean_abstract(text: str, url_place_holder: str = "URL") -> str:
    """
    Cleans the abstract by removing unnecessary elements such as MATH, dollar signs, and URLs.

    Args:
        text (str): The abstract text to clean.
        url_place_holder (str, optional): Placeholder for URLs. Defaults to "URL".

    Returns:
        str: The cleaned abstract.
    """
    text = text.replace("MATH", "")
    text = text.replace("$", "")
    text = text.replace("https : //", "https://")
    text = text.replace("http : //", "https://")
    text = re.sub("<a.*?>|</a>", "", text, flags=re.MULTILINE)  # remove <a href=''></a>
    text = re.sub(r"\S*https?:\S*", url_place_holder, text)  # replace https://xxx.com with URL
    return text.strip("\n").strip()


def remove_newlines_in_brackets(text: str) -> str:
    """
    Removes newline characters from the text, but only within pairs of curly brackets {}.

    Args:
        text (str): The input string which may contain newline characters inside and outside curly
        brackets.

    Returns:
        str: The modified string with newline characters removed only from within curly bracketed
        sections.
    """

    def _remove_newlines(match: re.Match) -> str:
        return match.group(0).replace("\n", "")

    return re.sub(r"{[^{}]*}", _remove_newlines, text)


def standardize_latexdiff_commands(text: str) -> str:
    """
    Standardizes LaTeX diff commands by removing unnecessary diff commands.

    Args:
        text (str): The LaTeX text to clean.

    Returns:
        str: The cleaned LaTeX text with standardized diff commands.
    """
    rgx_delbegin = r"\\DIFdelbegin\s*%DIFDELCMD < } %%%\s*\\DIFdelend"
    rgx_addbegin = r"\\DIFaddbegin\s*%DIFDELCMD < } %%%\s*\\DIFaddend"
    text = re.sub(rgx_delbegin, r"", text, re.DOTALL)
    text = re.sub(rgx_addbegin, r"", text, re.DOTALL)

    rgx_delbegin = r"(\\DIFdelbegin)[^\\]+?(?=\\DIFdel)"
    rgx_addbegin = r"(\\DIFaddbegin)[^\\]+?(?=\\DIFadd)"
    text = re.sub(rgx_delbegin, r"\1 ", text, re.DOTALL)
    text = re.sub(rgx_addbegin, r"\1 ", text, re.DOTALL)

    rgx_delend = r"(\\DIFdel\{(?:\\}|[^\}])*\})([^\\]+)(\\DIFdelend)"
    rgx_addend = r"(\\DIFadd\{(?:\\}|[^\}])*\})([^\\]+)(\\DIFaddend)"
    text = re.sub(rgx_delend, r"\1 \3", text, re.DOTALL)
    text = re.sub(rgx_addend, r"\1 \3", text, re.DOTALL)

    rgx_delend = r"(\\DIFdel\{(?:\\}|[^\}])*\})([^\\]+)(\\DIFdel)"
    rgx_addend = r"(\\DIFadd\{(?:\\}|[^\}])*\})([^\\]+)(\\DIFadd)"
    text = re.sub(rgx_delend, r"\1 \3", text, re.DOTALL)
    text = re.sub(rgx_addend, r"\1 \3", text, re.DOTALL)

    text = text.replace("\DIFdelbegin", "")
    text = text.replace("\DIFdelend", "")
    text = text.replace("\DIFaddbegin", "")
    text = text.replace("\DIFaddend", "")
    text = text.replace("\\begin{abstract}", "")
    text = text.replace("\\end{abstract}", "")
    return text


def strip_latex_command(text: str) -> str:
    """
    Removes LaTeX commands from the text while keeping content inside specified commands.

    Args:
        text (str): The LaTeX text to strip commands from.

    Returns:
        str: The cleaned text with LaTeX commands removed.
    """

    def _strip(matched: re.Match) -> str:
        excludes = set(["DIFdel", "DIFadd"])
        command_name = matched.group(1)
        content = matched.group(2)
        if command_name in excludes:
            return matched.group(0)
        return content

    rgx_command = r"\\([\w\d]+)\{(.*?)\}"
    stripped_text = re.sub(rgx_command, _strip, text, re.DOTALL)
    return stripped_text
