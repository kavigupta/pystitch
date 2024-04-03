from abc import ABC, abstractmethod

from imperative_stitch.parser.parse_python import fields_for_node
from imperative_stitch.utils.def_use_mask.names import VARIABLE_REGEX, match_either


class Handler(ABC):
    """
    Corresponds to a given node in the ns.SExpression AST.
    Keeps track of a set of defined production indices.
    """

    def __init__(self, mask, defined_production_idxs, config):
        self.mask = mask
        self.defined_production_idxs = defined_production_idxs
        self.config = config

    @abstractmethod
    def on_child_enter(self, position: int, symbol: int) -> "Handler":
        """
        When a child is entered, this method is called to determine the handler.

        Args:
            position: The position in the s-expression.
            symbol: The symbol of the child (index into a grammar's symbols list)
                Note: this can include variables, e.g., const-&x:0-Name,
                   but it can also include production symbols like Assign~S
                   or other leaves like const-i2~Const.

        Returns:
            The handler for the child.
        """
        return default_handler(
            symbol, self.mask, self.currently_defined_indices(), self.config
        )

    @abstractmethod
    def on_child_exit(self, position: int, symbol: int, child: "Handler"):
        """
        When a child is exited, this method is called to perform tasks related
            to the child.
        """

    def currently_defined_indices(self) -> set[int]:
        """
        Returns the set of currently defined symbols.
        """
        return self.defined_production_idxs

    @abstractmethod
    def is_defining(self, position: int) -> bool:
        """
        Returns whether the context at the given position is defining.

        E.g., for an Assign node, the left-hand side is defining, and
            the right-hand side is not. This is important because for
            defining contexts, we do not need to use a previously
            defined variable.
        """

    def currently_defined_names(self):
        """
        Return the set of currently defined names. Note that this
            isn't the set of production symbols like const-&x:0-Name,
            but rather a set of names like x.
        """
        names = set()
        for symbol in self.currently_defined_indices():
            sym, _ = self.mask.tree_dist.symbols[symbol]
            mat = match_either(sym)
            if not mat:
                assert VARIABLE_REGEX.match(sym), f"Could not match {sym}"
                continue
            names.add(mat.group("name"))
        return names

    def target_child(self, symbol: int) -> "Handler":
        """
        Return a handler collecting targets for the given child.
        """
        # pylint: disable=cyclic-import
        from .target_handler import create_target_handler

        return create_target_handler(
            symbol, self.mask, self.currently_defined_indices(), self.config
        )


class ConstructHandler(Handler):
    """
    Handler for a single construct.
    """

    # must be overridden in subclasses, represents the name of the construct
    name: str = None

    def __init__(self, mask, defined_production_idxs, config):
        super().__init__(mask, defined_production_idxs, config)
        assert isinstance(self.name, str)
        self.child_fields = {
            field: i for i, field in enumerate(fields_for_node(self.name))
        }


class DefaultHandler(Handler):
    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return super().on_child_enter(position, symbol)

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        pass

    def is_defining(self, position: int) -> bool:
        return False


def default_handler(symbol: int, mask, defined_production_idxs, config) -> Handler:
    # pylint: disable=cyclic-import
    from .abstraction_handler import AbstractionHandler
    from .defining_statement_handler import defining_statement_handlers

    symbol, _ = mask.tree_dist.symbols[symbol]
    if symbol.startswith("fn_"):
        return AbstractionHandler(mask, defined_production_idxs, config, symbol)

    return defining_statement_handlers().get(symbol, DefaultHandler)(
        mask, defined_production_idxs, config
    )
