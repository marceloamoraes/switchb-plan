"""Keyword filter: does the extracted text look like a switchgear/switchboard doc?"""
import re

KEYWORD_PATTERN = re.compile(r"\b(switch\s*board|skids?)\b", re.IGNORECASE)


def is_match(text: str) -> bool:
    return KEYWORD_PATTERN.search(text) is not None
