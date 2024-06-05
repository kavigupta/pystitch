import re
from typing import List

import neurosym as ns

VARIABLE_REGEX = re.compile(r"var-.*")


class AbstractionHandler(ns.python_def_use_mask.Handler):
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

    The way this is accomplished is via the traverser field, which performs the
        traversal over the body of the abstraction. See AbstractionBodyTraverser
        for more information.

    handler_fn is used to create the default handler fn in the mask copy used to
        absorb the body of the abstraction. This is necessary because the handler
        could be something like a target handler.

    """

    def __init__(
        self,
        mask,
        defined_production_idxs,
        config,
        head_symbol,
        abstraction,
        position,
        handler_fn=ns.python_def_use_mask.default_handler,
    ):
        super().__init__(mask, defined_production_idxs, config)
        ordering = self.mask.tree_dist.ordering.compute_order(
            self.mask.name_to_id(head_symbol)
        )
        assert ordering is not None, f"No ordering found for {head_symbol}"
        self._traversal_order_stack = ordering[::-1]

        body = ns.to_type_annotated_ns_s_exp(
            abstraction.body, config.dfa, abstraction.dfa_root
        )

        self.traverser = AbstractionBodyTraverser(
            mask,
            config,
            body,
            lambda mask_copy, sym: handler_fn(
                position, sym, mask_copy, self.defined_production_idxs, self.config
            ),
        )

    def on_child_enter(
        self, position: int, symbol: int
    ) -> ns.python_def_use_mask.Handler:
        """
        Make sure to collect the children of the abstraction, so it can
            be iterated once the abstraction is fully processed.
        """
        assert (
            self._traversal_order_stack.pop() == position
        ), "Incorrect traversal order"
        underlying = self.traverser.last_handler.on_child_enter(
            self.traverser.current_position, symbol
        )
        return CollectingHandler(symbol, underlying)

    def on_child_exit(
        self, position: int, symbol: int, child: ns.python_def_use_mask.Handler
    ):
        self.traverser.last_handler.on_child_exit(
            self.traverser.current_position, symbol, child
        )
        self.traverser.new_argument(child.node)

    def is_defining(self, position: int) -> bool:
        return self.traverser.is_defining

    def currently_defined_indices(self) -> list[int]:
        return self.traverser.last_handler.currently_defined_indices()

    @property
    def defined_symbols(self):
        handler = self.traverser.last_handler
        return handler.defined_symbols if hasattr(handler, "defined_symbols") else set()


class AbstractionBodyTraverser:
    """
    This class is a coroutine that traverses the body of an abstraction.
        It does so via the ._body_handler coroutine, which is a generator that yields a
        boolean value indicating whether the current argument is defining a variable,
        and is sent the next node in the tree to process. This is done via a coroutine
        because that is the simplest way to have a recursive function that can pause.

    The coroutine iterates on a copy of the def-use mask, which is important because
        the original mask used to create the AbstractionHandler will be modified
        as the arguments to the abstraction are processed. The copy is created with
        a single handler, which is a default handler for the body.
    """

    def __init__(self, mask, config, body, create_handler):
        self.mask = mask
        self.config = config
        self.create_handler = create_handler

        self._task_stack = [("traverse", body, 0)]
        self._body_handler = self.body_traversal_coroutine()
        self._mask_copy = None
        self._is_defining = None
        self._position = None
        self._variables_to_reuse = {}

        self.new_argument(None)

    @property
    def last_handler(self):
        return self._mask_copy.handlers[-1]

    @property
    def current_position(self):
        assert self._position is not None
        return self._position

    @property
    def is_defining(self):
        assert self._is_defining is not None
        return self._is_defining

    def task_coroutine(self):
        print(self._task_stack)
        while self._task_stack:
            task_type = self._task_stack[-1][0]
            if task_type == "traverse":
                yield from self.body_traversal_coroutine()
            elif task_type == "exit":
                yield from self.exit_coroutine()
            else:
                raise ValueError(f"Unrecognized task type {task_type}")

    def body_traversal_coroutine(self):
        _, node, position = self._task_stack.pop()
        if VARIABLE_REGEX.match(node.symbol):
            assert (
                self._mask_copy is not None
            ), "We do not support the identity abstraction"
            yield from self.handle_variable(node, position)
            return
        sym = self.mask.name_to_id(node.symbol)
        root = self._mask_copy is None
        if root:
            self._mask_copy = self.mask.with_handler(
                lambda mask_copy: self.create_handler(mask_copy, sym)
            )
        else:
            self._mask_copy.on_entry(position, sym)
        order = self.mask.tree_dist.ordering.order(sym, len(node.children))
        if not root:
            self._task_stack.append(("exit", sym, position))
        for i in order[::-1]:
            self._task_stack.append(("traverse", node.children[i], i))
        yield from self.task_coroutine()

    def handle_variable(self, node, position):
        # If the node is a variable, check if it is one that has already been processed
        name = node.symbol
        if name in self._variables_to_reuse:
            self._task_stack.append(
                ("traverse", self._variables_to_reuse[name], position)
            )
            yield from self.body_traversal_coroutine()
        else:
            is_defining = self._mask_copy.handlers[-1].is_defining(position)
            node = yield is_defining, position
            self._variables_to_reuse[name] = node

    def exit_coroutine(self):
        _, sym, position = self._task_stack.pop()
        self._mask_copy.on_exit(position, sym)
        yield from []

    def new_argument(self, node):
        """
        Iterate through the body of the abstraction, and set the _is_defining and _position values.

        Args:
            node: The node to send to the coroutine. None if the coroutine is just starting,
                otherwise the argument that was just processed.
        """
        try:
            self._is_defining, self._position = self._body_handler.send(node)
        except StopIteration:
            pass


class CollectingHandler(ns.python_def_use_mask.Handler):
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
        sym, arity = self.mask.id_to_name_and_arity(self.sym)
        assert (
            len(self.children) == arity
        ), f"{sym} expected {arity} children, got {len(self.children)}"
        return ns.SExpression(
            sym, [self.children[i].node for i in range(len(self.children))]
        )

    def on_enter(self):
        self.underlying_handler.on_enter()

    def on_exit(self):
        self.underlying_handler.on_exit()

    def on_child_enter(
        self, position: int, symbol: int
    ) -> ns.python_def_use_mask.Handler:
        return CollectingHandler(
            symbol, self.underlying_handler.on_child_enter(position, symbol)
        )

    def on_child_exit(
        self, position: int, symbol: int, child: ns.python_def_use_mask.Handler
    ):
        self.children[position] = child
        self.underlying_handler.on_child_exit(position, symbol, child)

    def is_defining(self, position: int) -> bool:
        return self.underlying_handler.is_defining(position)

    @property
    def defined_symbols(self):
        return self.underlying_handler.defined_symbols

    def compute_mask(
        self,
        position: int,
        symbols: List[int],
        idx_to_name: List[str],
        special_case_predicates: List[
            ns.python_def_use_mask.SpecialCaseSymbolPredicate
        ],
    ):
        return self.underlying_handler.compute_mask(
            position, symbols, idx_to_name, special_case_predicates
        )


class AbstractionHandlerPuller(ns.python_def_use_mask.HandlerPuller):
    def __init__(self, abstractions):
        self.abstractions = abstractions

    def pull_handler(
        self, position, symbol, mask, defined_production_idxs, config, handler_fn
    ):
        abstraction = self.abstractions["~".join(symbol.split("~")[:-1])]
        return AbstractionHandler(
            mask,
            defined_production_idxs,
            config,
            symbol,
            abstraction,
            position,
            handler_fn,
        )
