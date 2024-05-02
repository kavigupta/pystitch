from dataclasses import dataclass


@dataclass
class ExtraVar:
    """
    Used to represent an extra variable, not found in the tree distribution.

    Used in handling De Bruijn variables.
    """

    id: int
