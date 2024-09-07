import difflib
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
    Example:
        >>> get_time_range(2)
        ('2022-09-05T14:48:55.123456', '2024-09-05T14:48:55.123456')
    """
    my_date = datetime.now()
    end = my_date.isoformat()
    start_date = my_date.replace(year=my_date.year - years_back)
    start = start_date.isoformat()
    return start, end


def read_data(file_path: str) -> List[str]:
    """
    Reads data from a JSON file where each line is a separate JSON object.

    Args:
        file_path (str): The path to the JSON file to read.

    Returns:
        list: A list of parsed JSON objects or an empty list if the file is empty or an error occurs.
    """
    lines = []
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
    text_clean = text.translate(str.maketrans("", "", string.punctuation))
    return text_clean.strip()


def diff_strings(a, b):
    matcher = difflib.SequenceMatcher(None, a, b)
    eid = 0
    outs = []
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == "insert":
            text = clean_unused(b[b0:b1])
            if len(text) > 0:
                eid += 1
                outs.append(text)
        elif opcode == "delete":
            text = clean_unused(a[a0:a1])
            if len(text) > 0:
                eid += 1
                outs.append(text)
        elif opcode == "replace":
            textb = clean_unused(b[b0:b1])
            texta = clean_unused(a[a0:a1])
            if len(texta) > 0 or len(textb) > 0:
                eid += 1
                outs.append(texta)
                outs.append(textb)
    return eid, outs


def most_frequent(List):
    counter = 0
    num = List[0]
    for i in List:
        curr_frequency = List.count(i)
        if curr_frequency > counter:
            counter = curr_frequency
            num = i
    return num


def remove_duplicates(l):
    l.sort(key=lambda x: x["timestamp"])
    seen = set()
    new_l = []
    for d in l:
        t = tuple(d.items())
        if t not in seen:
            seen.add(t)
            new_l.append(d)
    return new_l


def clean_text(text: str, domain: str) -> str:
    try:
        if domain == "wikipedia":
            eid = re.search("\n See also", text).start()
        if domain == "wikinews":
            eid = re.search("Sources", text).start()
    except:
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


def clean_abstract(text):
    text = text.replace("MATH", "")
    text = text.replace("$", "")
    text = text.replace("https : //", "https://")
    text = text.replace("http : //", "https://")
    text = re.sub("<a.*?>|</a>", "", text, flags=re.MULTILINE)  # remove <a href=''></a>
    text = re.sub(r"\S*https?:\S*", "URL", text)  # replace https://xxx.com with URL
    return text.strip("\n").strip()
