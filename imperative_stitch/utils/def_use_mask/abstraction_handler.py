import neurosym as ns

from imperative_stitch.utils.def_use_mask.names import VARIABLE_REGEX

from .handler import Handler, default_handler


class AbstractionHandler(Handler):
    """
    Handler for an abstraction node. This effectively runs through
        the body of the abstraction, pausing at each abstraction variable
        to wait for the next node in the tree to be processed.

    E.g., in an abstraction node (fn_1 (Constant i2 1) &x:0), where fn_1 has body
            (Assign (Name %1 Store) #0)
        the handler would traverse Assign then Name, then pause, awaiting the
            next argument to be passed in. It would then get &x:0 passed in [since
            abstractions are processed in a custom order related to the ordering
            of the arguments' appearances in the body], and continue traversing,
            substituting &x:0 for the passed in node.

    The way this is accomplished is via the _body_handler coroutine, which yields
        a boolean value indicating whether the current argument is defining a variable,
        and is sent the next node in the tree to process. This is done via a coroutine
        because that is the simplest way to have a recursive function that can pause.

    The coroutine iterates on a copy of the def-use mask, which is important because
        the original mask used to create the AbstractionHandler will be modified
        as the arguments to the abstraction are processed. The copy is created with
        a single handler, which is a default handler for the body.

    """

    def __init__(self, mask, defined_production_idxs, config, head_symbol):
        super().__init__(mask, defined_production_idxs, config)
        self._traversal_order_stack = self.mask.tree_dist.ordering.compute_order(
            self.mask.tree_dist.symbol_to_index[head_symbol]
        )[::-1]
        head_symbol = "~".join(head_symbol.split("~")[:-1])
        self.abstraction = config.abstractions[head_symbol]
        self.body = self.abstraction.body.to_type_annotated_ns_s_exp(
            config.dfa, self.abstraction.dfa_root
        )
        self.mask_copy = self.mask.with_handler(
            lambda mask_copy: default_handler(
                0, mask_copy, defined_production_idxs, self.config
            )
        )
        self._body_handler = self.body_traversal_coroutine(self.body, 0)
        self._is_defining = None
        self._variables_to_reuse = {}

        self._iterate_body(None)

    def on_child_enter(self, position: int, symbol: int) -> "Handler":
        """
        Make sure to collect the children of the abstraction, so it can
            be iterated once the abstraction is fully processed.
        """
        assert (
            self._traversal_order_stack.pop() == position
        ), "Incorrect traversal order"
        return CollectingHandler(
            symbol,
            super().on_child_enter(position, symbol),
        )

    def on_child_exit(self, position: int, symbol: int, child: "Handler"):
        self._iterate_body(child.node)

    def is_defining(self, position: int) -> bool:
        assert self._is_defining is not None
        return self._is_defining

    def body_traversal_coroutine(self, node, position):
        if VARIABLE_REGEX.match(node.symbol):
            # If the node is a variable, check if it is one that has already been processed
            name = node.symbol
            if name in self._variables_to_reuse:
                node = self._variables_to_reuse[name]
            else:
                is_defining = self.mask_copy.handlers[-1].is_defining(position)
                node = yield is_defining
                self._variables_to_reuse[name] = node
        sym = self.mask.tree_dist.symbol_to_index[node.symbol]
        self.mask_copy.on_entry(position, sym)
        order = self.mask.tree_dist.ordering.order(sym, len(node.children))
        for i in order:
            yield from self.body_traversal_coroutine(node.children[i], i)
        self.mask_copy.on_exit(position, sym)

    def _iterate_body(self, node):
        """
        Iterate through the body of the abstraction, and set the is_defining value.

        Args:
            node: The node to send to the coroutine. None if the coroutine is just starting,
                otherwise the argument that was just processed.
        """
        try:
            self._is_defining = self._body_handler.send(node)
        except StopIteration:
            pass

    def currently_defined_indices(self) -> set[int]:
        return self.mask_copy.handlers[-1].currently_defined_indices()


class CollectingHandler(Handler):
    """
    Wrapper around another handler that collects the node as it is being created.
    """

    def __init__(self, sym, underlying_handler):
        super().__init__(
            underlying_handler.mask,
            underlying_handler.currently_defined_indices(),
            underlying_handler.config,
        )
        self.underlying_handler = underlying_handler
        self.sym: int = sym
        self.children = {}

    @property
    def node(self):
        sym, arity = self.mask.tree_dist.symbols[self.sym]
        assert (
            len(self.children) == arity
        ), f"Expected {arity} children, got {len(self.children)}"
        return ns.SExpression(
            sym, [self.children[i].node for i in range(len(self.children))]
        )

    def on_enter(self):
        self.underlying_handler.on_enter()

    def on_exit(self):
        self.underlying_handler.on_exit()

    def on_child_enter(self, position: int, symbol: int) -> Handler:
        return CollectingHandler(
            symbol, self.underlying_handler.on_child_enter(position, symbol)
        )

    def on_child_exit(self, position: int, symbol: int, child: Handler):
        self.children[position] = child
        self.underlying_handler.on_child_exit(position, symbol, child)

    def is_defining(self, position: int) -> bool:
        return self.underlying_handler.is_defining(position)

    @property
    def defined_symbols(self):
        return self.underlying_handler.defined_symbols
