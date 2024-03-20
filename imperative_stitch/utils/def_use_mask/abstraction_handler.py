import copy

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
        self.mask_copy.handlers.append(
            DefaultHandler.of(
                self.mask_copy,
                self.mask_copy.handlers[-1].valid_symbols,
                self.config,
                0,  # dosent' matter
            )
        )
        self.mask_copy.on_entry(
            0, self.mask.tree_dist.symbol_to_index[self.body.symbol]
        )
        self._body_handler = self.body_traversal_coroutine(self.body)
        self._argument_handlers = {}  # map from argument to handler

    def on_enter(self):
        try:
            print(
                "Before",
                [
                    self.mask_copy.tree_dist.symbols[x][0]
                    for x in self.mask_copy.handlers[-1].valid_symbols
                ],
            )
            next(self._body_handler)
        except StopIteration:
            pass
        print(
            "After",
            [
                self.mask_copy.tree_dist.symbols[x][0]
                for x in self.mask_copy.handlers[-1].valid_symbols
            ],
        )

    def on_exit(self):
        self.valid_symbols |= self.mask_copy.handlers[-1].valid_symbols

    def on_child_enter(self, position: int, symbol: int) -> "Handler":
        raise NotImplementedError

    def on_child_exit(self, position: int, symbol: int, child: "Handler"):
        raise NotImplementedError

    def is_defining(self, position: int) -> bool:
        raise NotImplementedError

    def body_traversal_coroutine(self, node):
        sym = self.mask.tree_dist.symbol_to_index[node.symbol]
        order = self.mask.tree_dist.ordering.order(sym, len(node.children))
        for i in order:
            child_sym = self.mask.tree_dist.symbol_to_index[node.children[i].symbol]
            self.mask_copy.on_entry(i, child_sym)
            yield from self.body_traversal_coroutine(node.children[i])
            self.mask_copy.on_exit(i, child_sym)
