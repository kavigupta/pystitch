from dataclasses import dataclass


class NotApplicable(Exception):
    pass


@dataclass
class MultipleExits(NotApplicable):
    pass


@dataclass
class NonInitializedInputs(NotApplicable):
    pass


@dataclass
class NonInitializedOutputs(NotApplicable):
    pass


@dataclass
class ClosureOverVariableModifiedInNonExtractedCode(NotApplicable):
    pass
