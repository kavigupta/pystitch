import ast
from collections import defaultdict

from python_graphs.instruction import Instruction

from imperative_stitch.analyze_program.ssa.banned_component import (
    BannedComponentVisitor,
)

from .ivm import Argument, DefinedIn, Phi, SSAVariableIntermediateMapping, Uninitialized
from .renamer import get_node_order, name_vars


class FunctionSSAAnnotator:
    """
    Annotates a control flow graph with SSA variables.

    Fields:
        _mapping: The mapping from SSA variables to their original symbols and parents.
        _start: A mapping from name to variable at the inlet to that node
        _end: A mapping from name to variable at the outlet of that node
    """

    def __init__(self, scope_info, entry_point):
        self.function_astn = entry_point.node
        BannedComponentVisitor().visit(self.function_astn)

        [first_block] = entry_point.next
        if first_block.control_flow_nodes:
            self.first_cfn = first_block.control_flow_nodes[0]
        else:
            self.first_cfn = NoControlFlowNode()

        function_scope = scope_info.function_scope_for(self.function_astn)
        if function_scope is None:
            self.function_symbols = []
            self.function_arguments = []
            self.function_argument_symbols = []
        else:
            self.function_symbols = sorted(
                function_scope.variables.all_symbols, key=str
            )
            self.function_arguments = sorted(
                function_scope.variables.arguments, key=lambda x: x.arg
            )
            self.function_argument_symbols = [x.arg for x in self.function_arguments]

        self._mapping = SSAVariableIntermediateMapping()
        self._start = {}
        self._end = {}

        self._arg_node = {}
        for sym in self.function_symbols:
            self._arg_node[sym] = self._mapping.fresh_variable(
                sym,
                Argument()
                if sym in self.function_argument_symbols
                else Uninitialized(),
            )

        self.node_order = get_node_order(self.function_astn)

    def run(self):
        """
        Run the SSA annotator.

        Returns:
            start: A mapping from control flow node to a mapping from symbol to variable at the inlet to that node.
            end: A mapping from control flow node to a mapping from symbol to variable at the outlet of that node.
            phi_map: A mapping from variable to its origin.
            annotations: A mapping from node to its variable.
        """
        all_cfns = self.sort_cfns(get_all_cfns(self.first_cfn))
        while True:
            start, end = self._start.copy(), self._end.copy()
            for cfn in all_cfns:
                self._process(cfn)
            if start == self._start and end == self._end:
                break
        annotations = self.collect_annotations()
        ordered_cfns = self.sort_cfns(self._start.keys())

        ordered_values = self._mapping.initials() + [
            v
            for cfn in ordered_cfns
            for v in [*self._start[cfn].values(), *self._end[cfn].values()]
        ]

        remapping = name_vars(self._mapping.original_symbol_of, ordered_values)
        start, end = [
            {
                cfn: {sym: remapping[sym_to_var[sym]] for sym in sym_to_var}
                for cfn, sym_to_var in x.items()
            }
            for x in [self._start, self._end]
        ]
        annotations = {
            node: [remapping[var] for var in vars] for node, vars in annotations.items()
        }

        return start, end, self._mapping.export_parents(remapping), annotations

    def collect_annotations(self):
        annotations = defaultdict(list)
        argument_to_var = self._mapping.arguments_map()
        for argument in self.function_arguments:
            annotations[argument].append(argument_to_var[argument.arg])
        for cfn in self._start:
            s, e = self._start[cfn], self._end[cfn]
            for astn in cfn.instruction.get_reads():
                astn = get_nodes_for_reads(astn)
                if astn.id in s:
                    annotations[astn].append(s[astn.id])
            for astn, name in self.get_writes_for(cfn):
                if name in e:
                    annotations[astn].append(e[name])
        return dict(annotations.items())

    def get_reads_for(self, cfn):
        result = []
        for astn in cfn.instruction.get_reads():
            result.append(get_nodes_for_reads(astn))
        result = self.sort_nodes(result)
        return result

    def get_writes_for(self, cfn):
        result = []
        for write in cfn.instruction.get_writes():
            result.extend(get_nodes_for_write(write))
        result = sorted(result, key=lambda x: self.node_order.get(x[0], -1))
        return result

    def _process(self, cfn):
        """
        Process the node `cfn` because one of its parents was updated.

        Will update both the start and end variables for `cfn` and
            add its children to the queue if the `end` variables for
            `cfn` changed.
        """
        # recompute since a parent was updated
        old_start = self._start.get(cfn, {})
        self._start[cfn] = {}
        for sym in self.function_symbols:
            parent_vars = set()
            for parent_end in self.prev_ends(cfn):
                if sym in parent_end:
                    parent_vars.add(parent_end[sym])
            parent_vars = sorted(parent_vars)
            if len(parent_vars) == 1:
                [self._start[cfn][sym]] = parent_vars
            else:
                self._start[cfn][sym] = self._mapping.fresh_variable_if_needed(
                    sym, Phi(parent_vars), old_start.get(sym, None)
                )
        new_end = self._ending_variables(cfn, self._start[cfn], self._end.get(cfn, {}))
        if cfn not in self._end or new_end != self._end[cfn]:
            self._end[cfn] = new_end

    def prev_ends(self, cfn):
        """
        Returns the end variables for each of the parents of `cfn`.
        """
        result = [self._end.get(parent, {}) for parent in self.sort_cfns(cfn.prev)]
        if cfn == self.first_cfn:
            result.append(self._arg_node)
        return result

    def sort_cfns(self, cfns):
        return sorted(cfns, key=lambda x: self.node_order.get(x.instruction.node, -1))

    def sort_nodes(self, nodes):
        return sorted(nodes, key=lambda x: self.node_order.get(x, -1))

    def _ending_variables(self, cfn, start_variables, current_end):
        """
        Compute the end variables for `cfn` given the start variables and the current end variables.
        """
        end_variables = start_variables.copy()
        for _, x in self.get_writes_for(cfn):
            end_variables[x] = self._mapping.fresh_variable_if_needed(
                x, DefinedIn(cfn), current_end.get(x, None)
            )
        return end_variables


class NoControlFlowNode:
    @property
    def prev(self):
        return []

    @property
    def next(self):
        return []

    @property
    def instruction(self):
        return Instruction(ast.Pass())


def run_ssa(scope_info, entry_point):
    annot = FunctionSSAAnnotator(scope_info, entry_point)
    return annot.run()


def get_nodes_for_reads(astn):
    if isinstance(astn, tuple) and astn[0] == "read":
        astn = astn[1]
    return astn


def get_nodes_for_write(node):
    if isinstance(node, tuple) and node[0] == "write":
        if isinstance(node[1], str):
            return get_nodes_for_write(node[2])
        return get_nodes_for_write(node[1])
    if isinstance(node, ast.Name):
        name = node.id
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        name = node.name
    elif isinstance(node, ast.For):
        return get_nodes_for_write(node.target)
    elif isinstance(node, ast.ExceptHandler):
        name = node.name
    else:
        raise Exception(f"Unexpected write: {node}")
    return [(node, name)]


def get_all_cfns(cfn):
    result = {cfn}
    fringe = [cfn]
    while fringe:
        cfn = fringe.pop()
        for next_cfn in cfn.next:
            if next_cfn not in result:
                result.add(next_cfn)
                fringe.append(next_cfn)
    return result
