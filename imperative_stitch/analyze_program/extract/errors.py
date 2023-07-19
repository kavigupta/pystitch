from dataclasses import dataclass


class NotApplicable(Exception):
    pass


@dataclass
class MultipleExits(NotApplicable):
    pass


@dataclass
class NonInitializedInputsOrOutputs(NotApplicable):
    pass


@dataclass
class ClosureOverVariableModifiedInExtractedCode(NotApplicable):
    pass


@dataclass
class ClosedVariablePassedDirectly(NotApplicable):
    pass


@dataclass
class ModifiesVariableClosedOverInNonExtractedCode(NotApplicable):
    pass
