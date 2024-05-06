from dataclasses import dataclass


@dataclass(frozen=True, eq=True, order=True)
class ExtraVar:
    """
    Used to represent an extra variable, not found in the tree distribution.

    Used in handling De Bruijn variables.
    """

    id: int
