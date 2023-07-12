import ast
from collections import defaultdict


from ..structures.per_function_cfg import PerFunctionCFG, eventually_accessible_cfns

from .ivm import (
    Argument,
    DefinedIn,
    Gamma,
    Phi,
    SSAVariableIntermediateMapping,
    Uninitialized,
)
from .renamer import name_vars
from .compute_node_to_containing import compute_enclosed_variables


class FunctionSSAAnnotator:
    """
    Annotates a control flow graph with SSA variables.

    Fields:
        _mapping: The mapping from SSA variables to their original symbols and parents.
        _start: A mapping from name to variable at the inlet to that node
        _end: A mapping from name to variable at the outlet of that node
    """

    def __init__(self, scope_info, per_function_cfg: PerFunctionCFG):
        self.scope_info = scope_info
        self.graph = per_function_cfg

        function_scope = scope_info.function_scope_for(self.graph.function_astn)
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

    def run(self):
        """
        Run the SSA annotator.

        Returns:
            start: A mapping from control flow node to a mapping from symbol to variable at the inlet to that node.
            end: A mapping from control flow node to a mapping from symbol to variable at the outlet of that node.
            phi_map: A mapping from variable to its origin.
            annotations: A mapping from node to its variable.
        """
        while True:
            start, end = self._start.copy(), self._end.copy()
            queue = [self.graph.first_cfn]
            while queue:
                cfn = queue.pop()
                if self._process(cfn):
                    queue.extend(self.graph.sort_by_cfn_key(cfn.next))
            if start == self._start and end == self._end:
                break
        annotations = self.collect_annotations()
        ordered_cfns = self.graph.sort_by_cfn_key(self._start.keys())

        ordered_values = self._mapping.initials() + [
            v
            for cfn in ordered_cfns
            for v in [*self._start[cfn].values(), *self._end[cfn].values()]
        ]

        immediately_executed, closed = compute_enclosed_variables(
            self.scope_info, self.graph, annotations
        )

        for node in immediately_executed:
            annotations[node] = [self._start[self.graph.astn_to_cfn[node]][node.id]]

        for node in closed:
            annotations[node] = [self.add_gamma(node)]
            ordered_values += annotations[node]

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

    def add_gamma(self, node):
        """
        Add a gamma parent to the IVM and return the handle for the given node.
        """
        cfn = self.graph.astn_to_cfn[node]
        cfns = eventually_accessible_cfns(self.graph.next_cfns_of, {cfn})
        cfns = [x for x in cfns if x in self._start]
        cfns = self.graph.sort_by_cfn_key(cfns)
        closed = [
            x
            for cfn in cfns
            for x in [self._start[cfn][node.id], self._end[cfn][node.id]]
        ]
        current = self._start[cfn][node.id]
        closed = tuple(sorted(set(closed)))
        if closed == (current,):
            return current
        fresh_var = self._mapping.fresh_variable(node.id, Gamma(node, closed))
        return fresh_var

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
        result = self.graph.sort_by_astn_key(result, lambda x: x)
        return result

    def get_writes_for(self, cfn):
        result = []
        for write in cfn.instruction.get_writes():
            result.extend(get_nodes_for_write(write))
        result = self.graph.sort_by_astn_key(result, lambda x: x[0])
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
                    sym,
                    Phi(cfn.instruction.node, tuple(parent_vars)),
                    old_start.get(sym, None),
                )
        new_end = self._ending_variables(cfn, self._start[cfn], self._end.get(cfn, {}))
        if cfn not in self._end or new_end != self._end[cfn]:
            self._end[cfn] = new_end
            return True
        return False

    def prev_ends(self, cfn):
        """
        Returns the end variables for each of the parents of `cfn`.
        """
        result = [
            self._end.get(parent, {}) if parent is not None else self._arg_node
            for parent in self.graph.sort_by_cfn_key(
                [x for _, x in self.graph.prev_cfns_of[cfn]]
            )
        ]
        return result

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


def run_ssa(scope_info, per_function_cfg: PerFunctionCFG):
    annot = FunctionSSAAnnotator(scope_info, per_function_cfg)
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
