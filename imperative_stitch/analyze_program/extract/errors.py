class NotApplicable(Exception):
    pass


class NonInitializedInputs(NotApplicable):
    pass


class NonInitializedOutputs(NotApplicable):
    pass


class UnexpectedControlFlowException(NotApplicable):
    pass
