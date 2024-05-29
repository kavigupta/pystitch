import ast
import uuid
from dataclasses import dataclass
from typing import List

import neurosym as ns
from frozendict import frozendict


(
    PythonAST,
    SequenceAST,
    NodeAST,
    ListAST,
    LeafAST,
    SliceElementAST,
    StarrableElementAST,
    SpliceAST,
) = (
    ns.PythonAST,
    ns.SequenceAST,
    ns.NodeAST,
    ns.ListAST,
    ns.LeafAST,
    ns.SliceElementAST,
    ns.StarrableElementAST,
    ns.SpliceAST,
)


@dataclass
class Variable(PythonAST):
    sym: str

    @property
    def idx(self):
        return int(self.sym[1:])

    def map(self, fn):
        return fn(self)

    def to_ns_s_exp(self, config=frozendict()):
        if config.get("no_leaves", False):
            return ns.SExpression("var-" + self.sym, [])
        return self.sym


@dataclass
class SymvarAST(Variable):
    def to_python_ast(self):
        return self.sym

    def _replace_with_substitute(self, arguments):
        return arguments.symvars[self.idx - 1]


@dataclass
class MetavarAST(Variable):
    def to_python_ast(self):
        return ast.Name(id=self.sym)

    def _replace_with_substitute(self, arguments):
        return arguments.metavars[self.idx]


@dataclass
class ChoicevarAST(Variable):
    def to_python_ast(self):
        return ast.Name(id=self.sym)

    def _replace_with_substitute(self, arguments):
        return SpliceAST(arguments.choicevars[self.idx])


@dataclass
class AbstractionCallAST(PythonAST):
    tag: str
    args: List[PythonAST]
    handle: uuid.UUID

    def to_ns_s_exp(self, config=frozendict()):
        return ns.SExpression(self.tag, [x.to_ns_s_exp(config) for x in self.args])

    def to_python_ast(self):
        raise RuntimeError("cannot convert abstraction call to python")

    def map(self, fn):
        return fn(
            AbstractionCallAST(self.tag, [x.map(fn) for x in self.args], self.handle)
        )
