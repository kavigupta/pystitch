import copy

import neurosym as ns

from imperative_stitch.utils.def_use_mask.names import VARIABLE_REGEX

from .handler import DefaultHandler, Handler


class AbstractionHandler(Handler):
    def __init__(self, mask, valid_symbols, config, head_symbol):
        super().__init__(mask, valid_symbols, config)
        head_symbol = "~".join(head_symbol.split("~")[:-1])
        self.abstraction = config.abstractions[head_symbol]
        self.body = self.abstraction.body.to_type_annotated_ns_s_exp(
            config.dfa, self.abstraction.dfa_root
        )
        self.mask_copy = copy.deepcopy(self.mask)
        self.injected_handler = DefaultHandler.of(
            self.mask_copy,
            self.valid_symbols,
            self.config,
            0,  # dosent' matter
        )
        self.mask_copy.handlers.append(self.injected_handler)
        self._body_handler = self.body_traversal_coroutine(self.body, 0)
        self._argument_handlers = {}  # map from argument to handler
        self._is_defining = None
        self._done_with_handler = False
        self._variables_to_reuse = {}

    def on_enter(self):
        try:
            print(
                "Before",
                [
                    self.mask_copy.tree_dist.symbols[x][0]
                    for x in self.mask_copy.handlers[-1].valid_symbols
                ],
            )
            self._is_defining = next(self._body_handler)
        except StopIteration:
            self._done_with_handler = True
        print(
            "After",
            [
                self.mask_copy.tree_dist.symbols[x][0]
                for x in self.mask_copy.handlers[-1].valid_symbols
            ],
        )

    def on_exit(self):
        assert self._done_with_handler
        assert self.injected_handler is self.mask_copy.handlers[-1]
        assert self.valid_symbols is self.injected_handler.valid_symbols

    def on_child_enter(self, position: int, symbol: int) -> "Handler":
        return CollectingHandler(
            symbol,
            super().on_child_enter(position, symbol),
        )

    def on_child_exit(self, position: int, symbol: int, child: "Handler"):
        try:
            self._is_defining = self._body_handler.send(child.node)
        except StopIteration:
            self._done_with_handler = True

    def is_defining(self, position: int) -> bool:
        print("is defining: ", self._is_defining, "position", position)
        print("valid symbols", self.valid_symbols)
        assert self._is_defining is not None
        return self._is_defining

    def body_traversal_coroutine(self, node, position):
        if VARIABLE_REGEX.match(node.symbol):
            name = node.symbol
            if name in self._variables_to_reuse:
                node = self._variables_to_reuse[name]
            else:
                is_defining = self.mask_copy.handlers[-1].is_defining(position)
                node = yield is_defining
                self._variables_to_reuse[name] = node
                print(
                    "filling variable", name, "with", node, "is_defining", is_defining
                )
            print(
                "current valid symbols",
                self.mask_copy.handlers[-1].valid_symbols,
                self.valid_symbols,
            )
        sym = self.mask.tree_dist.symbol_to_index[node.symbol]
        self.mask_copy.on_entry(position, sym)
        order = self.mask.tree_dist.ordering.order(sym, len(node.children))
        for i in order:
            yield from self.body_traversal_coroutine(node.children[i], i)
        self.mask_copy.on_exit(position, sym)


class CollectingHandler(Handler):
    def __init__(self, sym, underlying_handler):
        super().__init__(
            underlying_handler.mask,
            underlying_handler.valid_symbols,
            underlying_handler.config,
        )
        self.underlying_handler = underlying_handler
        self.sym: int = sym
        self.children = {}

    @property
    def node(self):
        sym, arity = self.mask.tree_dist.symbols[self.sym]
        assert len(self.children) == arity
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
