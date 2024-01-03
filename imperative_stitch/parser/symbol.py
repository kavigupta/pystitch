from dataclasses import dataclass

from ast_scope.scope import Scope

@dataclass(frozen=True)
class Symbol:
    """
    Represents a symbol, like &x:3. This means the symbol x in static frame 3.
    Can also represent a global symbol that's either a builtin or an imported
        value. This differs from a symbol defined in the block of code that happens
        to be in global scope, which will be given a static frame number.
    """

    name: str
    scope: Scope

    @classmethod
    def parse(cls, x):
        """
        Parses a symbol.
        """
        if x.startswith("&"):
            name, scope = x[1:].split(":")
            return cls(name, scope)
        if x.startswith("g"):
            assert x.startswith("g_")
            return cls(x[2:], None)
        return None

    def render(self):
        if self.scope is None:
            return f"g_{self.name}"
        return f"&{self.name}:{self.scope}"
