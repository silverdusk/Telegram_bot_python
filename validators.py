import os
import re
import logging
from dotenv import load_dotenv


load_dotenv()
min_len_str = os.getenv('MIN_LEN_STR')
max_len_str = os.getenv('MAX_LEN_STR')


def text_input_validator(message):
    result = re.search(r"^[A-Za-z0-9\s!\"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~]"
                       r"{" + str(min_len_str) + "," + str(max_len_str) + "}$", message.text)
    return result


def is_int(string):
    try:
        int(string)
        return True
    except ValueError:
        logging.error("Incorrect input value for int conversion: %s", string)
        return False


def is_float(string):
    try:
        float(string)
        return True
    except ValueError:
        logging.error("Incorrect input value for float conversion: %s", string)
        return False
