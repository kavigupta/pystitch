from dataclasses import dataclass


@dataclass
class ToBeSpliced:
    _fields = ["target"]
    elements: list
