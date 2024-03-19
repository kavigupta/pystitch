from ..handler import DefaultHandler


class JustAnExpressionHandler(DefaultHandler):
    """
    This is for LHS values where nothing is actually being defined (e.g., Subscript, Attribute, etc.)
    """

    def __init__(self, mask, valid_symbols, config):
        super().__init__(mask, valid_symbols, config)
        self.defined_symbols = set()
