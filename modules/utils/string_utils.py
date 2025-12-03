"""String manipulation utilities for TerraVision.

This module provides string processing functions for finding, replacing,
and cleaning text patterns in Terraform configurations.
"""

from typing import Optional


def find_between(
    text: str,
    begin: str,
    end: str,
    alternative: str = "",
    replace: bool = False,
    occurrence: int = 1,
) -> Optional[str]:
    """Extract text between two delimiters.

    Args:
        text: Source text
        begin: Starting delimiter
        end: Ending delimiter
        alternative: Replacement text if replace=True
        replace: Whether to replace found text
        occurrence: Which occurrence to find

    Returns:
        Text between delimiters or modified text if replace=True
    """
    if not text:
        return
    # Handle Nested Functions with multiple brackets in parameters
    if begin not in text and not replace:
        return ""
    elif begin not in text and replace:
        return text
    if end == ")":
        begin_index = text.find(begin)
        # begin_index = find_nth(text, begin, occurrence)
        end_index = find_nth(text, ")", occurrence)
        end_index = text.find(")", begin_index)
        middle = text[begin_index + len(begin) : end_index]
        num_brackets = middle.count("(")
        if num_brackets >= 1:
            end_index = find_nth(text, ")", num_brackets + 1)
            middle = text[begin_index + len(begin) : end_index]
        return middle
    else:
        middle = text.split(begin, 1)[1].split(end, 1)[0]
    # If looking for a space but no space found, terminate with any non alphanumeric char except _
    # so that variable names don't get broken up (useful for extracting variable names and locals)
    if (end == " " or end == "") and not middle.endswith(" "):
        for i in range(0, len(middle)):
            char = middle[i]
            if not char.isalpha() and char != "_" and char != "~":
                end = char
                middle = text.split(begin, 1)[1].split(end, 1)[0]
                break
    if replace:
        return text.replace(begin + middle, alternative, 1)
    else:
        return middle


def find_nth(string: str, substring: str, n: int) -> int:
    """Find nth occurrence of substring in string.

    Args:
        string: String to search
        substring: Substring to find
        n: Occurrence number (1-indexed)

    Returns:
        Index of nth occurrence
    """
    if n == 1:
        return string.find(substring)
    else:
        return string.find(substring, find_nth(string, substring, n - 1) + 1)
