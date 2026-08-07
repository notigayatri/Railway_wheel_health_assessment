def generate_id(prefix: str, number: int) -> str:
    """
    Generate formatted IDs.

    Example:
        generate_id("WH", 1)
        -> WH000001
    """

    return f"{prefix}{number:06d}"