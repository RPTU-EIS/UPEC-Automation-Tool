"""Utility functions not specific to frontend or backend. """
from difflib import SequenceMatcher


def sort_names_by_keywords(names: list[str], keywords: list[str]) -> list[str]:
    """Sorts a list of names based on their similarity with a list of keywords.

    The function prioritizes names that have full matches of the keywords. If multiple
    keywords fully match, the name gets an even higher priority. For partial matches,
    the function considers the degree of similarity between the name and the keywords.
    The more keywords resemble the name, the higher the priority.
    Used to suggest potential clock and reset signals, and to prioritize loading packages
    first when generating Tcl scripts

    Args:
        names: List of name strings to be sorted.
        keywords: List of keyword strings to sort the names by.

    Returns:
        List of names sorted by their similarity to the keywords.
    """

    def similarity(a, b):
        return SequenceMatcher(None, a, b).ratio()

    def name_priority(name):
        name_lower = name.lower()
        full_matches = sum(1 for keyword in keywords if keyword.lower() in name_lower)
        partial_matches = sum(similarity(name_lower, keyword.lower()) for keyword in keywords)
        return -full_matches, -partial_matches

    return sorted(names, key=name_priority)


def sort_signals_hierarchically(signal_list: list[str] | set[str] | dict[str, any]) -> list[str]:
    """Sorts signal names first by hierarchical depth and then alphabetically (case-insensitive).
    Signals of the top-level module will be listed first.

    Args:
        signal_list: List/Set/Dictionary of signal names to be sorted.

    Returns:
        List of sorted names."""
    return sorted(signal_list, key=lambda x: (x.count('.'), x.lower()))
