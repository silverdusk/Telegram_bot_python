"""Input validation utilities."""
import re
import logging
from datetime import datetime
from typing import Optional
import pytz
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def validate_text_input(text: str, min_len: Optional[int] = None, max_len: Optional[int] = None) -> bool:
    """
    Validate text input.
    
    Args:
        text: Text to validate
        min_len: Minimum length (uses config if None)
        max_len: Maximum length (uses config if None)
    
    Returns:
        True if valid, False otherwise
    """
    settings = get_settings()
    min_length = min_len if min_len is not None else settings.min_len_str
    max_length = max_len if max_len is not None else settings.max_len_str
    
    length_valid = min_length <= len(text) <= max_length
    character_valid = re.match(
        r"^[A-Za-z0-9\s!\"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~]+$",
        text
    ) is not None
    
    return length_valid and character_valid


def is_int(value: str) -> bool:
    """
    Check if string can be converted to integer.
    
    Args:
        value: String to check
    
    Returns:
        True if can be converted to int, False otherwise
    """
    try:
        int(value)
        return True
    except (ValueError, TypeError):
        logger.error(f"Incorrect input value for int conversion: {value}")
        return False


def is_float(value: str) -> bool:
    """
    Check if string can be converted to float.
    
    Args:
        value: String to check
    
    Returns:
        True if can be converted to float, False otherwise
    """
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        logger.error(f"Incorrect input value for float conversion: {value}")
        return False


def check_working_hours() -> bool:
    """
    Check if current time is within working hours.
    
    Returns:
        True if within working hours or skip_working_hours is enabled, False otherwise
    """
    settings = get_settings()
    
    if settings.skip_working_hours:
        return True
    
    try:
        now = datetime.now(pytz.timezone('Europe/Lisbon'))
        
        # Check if weekend
        if now.weekday() > 5:
            return False
        
        # Check if within working hours (9:30 - 19:00)
        if now.hour < 9:
            return False
        if now.hour > 19:
            return False
        if now.hour == 9 and now.minute < 30:
            return False
        
        return True
    except Exception as e:
        logger.error(f"Error checking working hours: {e}")
        return True  # Default to allowing if check fails

