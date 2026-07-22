"""
SENTINEL - Gas Intelligence Agent
Helper utilities for common operations.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
import uuid
import re


def generate_event_id() -> str:
    """
    Generate a unique event identifier.
    
    Returns:
        str: Unique event ID in format 'evt-{timestamp}-{uuid}'
    """
    timestamp = int(datetime.now(timezone.utc).timestamp())
    unique_id = str(uuid.uuid4())[:8]
    return f"evt-{timestamp}-{unique_id}"


def generate_batch_id() -> str:
    """
    Generate a unique batch identifier.
    
    Returns:
        str: Unique batch ID in format 'batch-{timestamp}-{uuid}'
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return f"batch-{timestamp}-{unique_id}"


def validate_zone_name(zone: str) -> bool:
    """
    Validate zone name format.
    
    Args:
        zone: Zone name to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not zone or len(zone) < 1 or len(zone) > 100:
        return False
    
    # Allow alphanumeric, hyphens, underscores, and spaces
    pattern = r'^[a-zA-Z0-9\-_\s]+$'
    return bool(re.match(pattern, zone))


def sanitize_string(value: str, max_length: int = 2000) -> str:
    """
    Sanitize string by removing control characters and limiting length.
    
    Args:
        value: String to sanitize
        max_length: Maximum allowed length
        
    Returns:
        str: Sanitized string
    """
    if not value:
        return ""
    
    # Remove control characters except newline and tab
    sanitized = "".join(char for char in value if char.isprintable() or char in "\n\t")
    
    # Limit length
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length-3] + "..."
    
    return sanitized


def clamp_value(value: float, min_val: float, max_val: float) -> float:
    """
    Clamp a value between minimum and maximum bounds.
    
    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value
        
    Returns:
        float: Clamped value
    """
    return max(min_val, min(value, max_val))


def calculate_percentage(value: float, total: float) -> float:
    """
    Calculate percentage safely.
    
    Args:
        value: Numerator
        total: Denominator
        
    Returns:
        float: Percentage (0-100)
    """
    if total == 0:
        return 0.0
    return (value / total) * 100.0


def format_timestamp(dt: datetime) -> str:
    """
    Format datetime to ISO 8601 string.
    
    Args:
        dt: Datetime to format
        
    Returns:
        str: ISO 8601 formatted timestamp
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()


def parse_timestamp(timestamp_str: str) -> Optional[datetime]:
    """
    Parse ISO 8601 timestamp string.
    
    Args:
        timestamp_str: ISO 8601 timestamp string
        
    Returns:
        Optional[datetime]: Parsed datetime or None if invalid
    """
    try:
        return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
    except (ValueError, AttributeError):
        return None


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deep merge two dictionaries.
    
    Args:
        base: Base dictionary
        override: Dictionary to merge into base
        
    Returns:
        Dict[str, Any]: Merged dictionary
    """
    result = base.copy()
    
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    
    return result


def truncate_list(lst: list, max_items: int = 100) -> list:
    """
    Truncate list to maximum number of items.
    
    Args:
        lst: List to truncate
        max_items: Maximum number of items
        
    Returns:
        list: Truncated list
    """
    if len(lst) > max_items:
        return lst[:max_items]
    return lst


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Safely convert value to float.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        float: Converted value or default
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    Safely convert value to int.
    
    Args:
        value: Value to convert
        default: Default value if conversion fails
        
    Returns:
        int: Converted value or default
    """
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def get_current_timestamp() -> datetime:
    """
    Get current UTC timestamp.
    
    Returns:
        datetime: Current UTC datetime
    """
    return datetime.now(timezone.utc)


def is_valid_number(value: Any) -> bool:
    """
    Check if value is a valid number.
    
    Args:
        value: Value to check
        
    Returns:
        bool: True if valid number, False otherwise
    """
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False