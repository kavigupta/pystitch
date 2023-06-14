from ast import AST
from dataclasses import dataclass


@dataclass
class ExtractionSite:
    node: AST
    body_field: str
    start: int
    end: int
