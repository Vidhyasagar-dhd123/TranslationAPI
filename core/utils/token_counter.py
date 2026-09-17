"""
Token calculation utility based on word count.
1 word = 1 token (configurable minimum of 1 token for non-empty text).
"""
import re


def count_tokens(text: str) -> int:
    """
    Counts tokens based on word tokens.
    Handles multiple languages, whitespace, and punctuation.
    """
    if not text or not text.strip():
        return 0
    
    # Split on whitespace and normalize
    words = re.findall(r'\S+', text.strip())
    token_count = len(words)
    return max(1, token_count)
