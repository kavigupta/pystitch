import ast
from collections import defaultdict

from python_graphs.control_flow import BasicBlock
from python_graphs.instruction import Instruction

from ..ssa.banned_component import BannedComponentVisitor
from ..ssa.renamer import get_node_order


class PerFunctionCFG:
    """
    A control flow graph for a function, includes some extra information.

    Fields:
        function_astn: The AST node for the function.
        entry_point: The entry point of the function (a BasicBlock).
        first_cfn: The first control flow node of the function.
        astn_order: A mapping from AST node to its preorder index in the AST
            Useful for determinism.
        prev_cfns_of: A mapping from control flow node to its predecessors.
            Includes exceptions.
        next_cfns_of: A mapping from control flow node to its successors.
            Includes exceptions.
    """

    def __init__(self, entry_point: BasicBlock):
        self.function_astn = entry_point.node
        BannedComponentVisitor().visit(self.function_astn)
        self.entry_point = entry_point
        [first_block] = entry_point.next
        if first_block.control_flow_nodes:
            self.first_cfn = first_block.control_flow_nodes[0]
        else:
            self.first_cfn = NoControlFlowNode()
        self.astn_order = get_node_order(self.function_astn)
        self.prev_cfns_of, self.next_cfns_of = compute_full_graph(self.first_cfn)

    def sort_by_astn_key(self, items, key=lambda x: x):
        """
        Sort the items by the AST node key. Puts None at
            the beginning and any node not in the AST after it

        Args:
            items: List[A] The items to sort.
            key: A function from A to AST node.

        Returns:
            List[A] The sorted items.
        """
        return sorted(
            items,
            key=lambda x: self.astn_order.get(key(x), -1) if x is not None else -2,
        )

    def sort_by_cfn_key(self, items, key=lambda x: x):
        """
        Sort the items by the control flow node key.

        Args:
            items: List[A] The items to sort.
            key: A function from A to control flow node.

        Returns:
            List[A] The sorted items.
        """
        return self.sort_by_astn_key(items, lambda x: key(x).instruction.node)


class NoControlFlowNode:
    """
    Represents a control flow node that does not exist.
    """

    @property
    def prev(self):
        return []

    @property
    def next(self):
        return []

    @property
    def instruction(self):
        return Instruction(ast.Pass())

    @property
    def block(self):
        return NoBlock()


class NoBlock:
    """
    Represents a block that does not exist.
    """

    @property
    def exits_from_middle(self):
        return set()


def compute_full_graph(first_cfn):
    """
    Compute the full graph of the control flow nodes, including exceptions.

    Args:
        first_cfn: The first control flow node of the function.

    Returns:
        prev: A mapping from control flow node to its predecessors. first_cfn -> None is added.
            Includes exceptions.
        next: A mapping from control flow node to its successors.
            Includes exceptions.
    """
    prev = defaultdict(set)
    next = defaultdict(set)
    # prev of first is None
    prev[first_cfn].add(None)
    seen = set()
    fringe = [first_cfn]
    while fringe:
        cfn = fringe.pop()
        if cfn in seen:
            continue
        seen.add(cfn)
        for next_cfn in cfn.next:
            prev[next_cfn].add(cfn)
            next[cfn].add(next_cfn)
            fringe.append(next_cfn)
        # exceptions
        if cannot_cause_exception(cfn):
            continue
        cfb = cfn.block
        # exception can happen in the middle, so prev can also be the root of the exception
        exception_causers = {cfn} | set(cfn.prev)
        if cfn is first_cfn:
            exception_causers.add(None)
        exception_targets = {
            exc_cfn
            for exc_cfb in cfb.exits_from_middle
            for exc_cfn in exc_cfb.control_flow_nodes
        }
        for exc_causer in exception_causers:
            for exc_target in exception_targets:
                prev[exc_target].add(exc_causer)
                next[exc_causer].add(exc_target)
    return prev, next


def cannot_cause_exception(cfn):
    """
    Returns True if the control flow node `cfn` cannot cause an exception.
    """
    # TODO implement this
    return False
