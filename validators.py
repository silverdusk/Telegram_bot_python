import re
import logging.config
import json


logging.config.fileConfig('logging.ini')
with open('config.json', 'r') as file:
    config = json.load(file)


def text_input_validator(message):
    min_len = config['min_len_str']
    max_len = config['max_len_str']

    length_valid = min_len <= len(message.text) <= max_len
    # pattern = r'^[A-Za-z0-9\s!"#$%&\'()*+,-.\/:;<=>?@\[\\\]^_`\}\{|~]{{{}, {}}}+$'.format(min_len, max_len)
    character_valid = re.match(r"^[A-Za-z0-9\s!\"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~]+$", message.text) is not None
    # result = re.search(pattern, message.text)
    return length_valid and character_valid


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


def check_working_hours():
    if config['skip_working_hours'] == 'True':
        return True
    now = datetime.datetime.now(pytz.timezone('Europe/Lisbon'))
    # now = datetime.datetime.now(pytz.timezone('Asia/Jerusalem'))
    # now = datetime.datetime.now(pytz.timezone('America/New_York'))
    if now.weekday() > 5:
        return False
    else:
        if now.hour < 9 or now.hour > 19:
            return False
        elif now.hour == 9 and now.minute < 30:
            return False
        else:
            return True
