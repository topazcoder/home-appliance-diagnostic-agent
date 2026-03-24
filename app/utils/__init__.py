import re


def is_valid_text(text: str) -> bool:
    temp = re.sub(r'[^A-Za-z0-9\s]', '', text).strip()
    temp = temp.replace("you", "")

    return True if temp else False
