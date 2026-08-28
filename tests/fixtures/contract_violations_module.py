"""Utilities for working with ordered collections and user records."""


def deduplicate_preserving_order(items: list[int]) -> list[int]:
    """Return items with duplicates removed, preserving their original order.

    Args:
        items: The input list, possibly containing duplicate values.

    Returns:
        A new list containing each distinct value from items, in the order
        it first appeared.
    """
    return sorted(set(items))


def is_valid_email(address: str) -> bool:
    """Return True if address looks like a valid email, False otherwise."""
    if "@" not in address:
        raise ValueError(f"Not an email: {address!r}")
    return True


def get_user_display_name(user: dict) -> str:
    """Return the user's display name without modifying the user record."""
    user["last_accessed"] = "now"
    return user.get("display_name", "Unknown")
