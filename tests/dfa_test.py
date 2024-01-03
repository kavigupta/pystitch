import ast
import unittest

from s_expression_parser import Pair, nil

from imperative_stitch.parser import ParserConfig, parse, python_to_s_exp
from imperative_stitch.utils.classify_nodes import TRANSITIONS, export_dfa
from imperative_stitch.utils.recursion import recursionlimit

from .utils import expand_with_slow_tests, small_set_examples

dfa = export_dfa(TRANSITIONS)

reasonable_classifications = [
    ("AnnAssign", "S"),
    ("Assert", "S"),
    ("Assign", "S"),
    ("AsyncFunctionDef", "S"),
    ("AsyncFor", "S"),
    ("AsyncWith", "S"),
    ("Attribute", "E"),
    ("Attribute", "L"),
    ("AugAssign", "S"),
    ("Await", "E"),
    ("BinOp", "E"),
    ("BoolOp", "E"),
    ("Call", "E"),
    ("ClassDef", "S"),
    ("Compare", "E"),
    ("Constant", "E"),
    ("Constant", "F"),
    ("Constant", "X"),
    ("Delete", "S"),
    ("Dict", "E"),
    ("DictComp", "E"),
    ("ExceptHandler", "EH"),
    ("Expr", "S"),
    ("For", "S"),
    ("FormattedValue", "F"),
    ("FunctionDef", "S"),
    ("GeneratorExp", "E"),
    ("Global", "S"),
    ("If", "S"),
    ("IfExp", "E"),
    ("Import", "S"),
    ("ImportFrom", "S"),
    ("JoinedStr", "E"),
    ("JoinedStr", "X"),
    ("Lambda", "E"),
    ("List", "E"),
    ("List", "L"),
    ("ListComp", "E"),
    ("Module", "M"),
    ("Name", "E"),
    ("Name", "L"),
    ("Name", "X"),
    ("NamedExpr", "E"),
    ("Nonlocal", "S"),
    ("Raise", "S"),
    ("Return", "S"),
    ("Set", "E"),
    ("SetComp", "E"),
    ("Slice", "E"),
    ("Starred", "E"),
    ("Subscript", "E"),
    ("Subscript", "L"),
    ("Try", "S"),
    ("Tuple", "E"),
    ("Tuple", "L"),
    ("UnaryOp", "E"),
    ("While", "S"),
    ("With", "S"),
    ("Yield", "E"),
    ("YieldFrom", "E"),
    ("alias", "X"),
    ("arg", "A"),
    ("arg", "X"),
    ("arguments", "As"),
    ("comprehension", "C"),
    ("keyword", "K"),
    ("list", "A"),
    ("list", "C"),
    ("list", "E"),
    ("list", "EH"),
    ("list", "F"),
    ("list", "K"),
    ("list", "L"),
    ("list", "W"),
    ("list", "X"),
    ("semi", "S"),
    ("withitem", "W"),
]


def to_list_nested(x):
    if x is nil:
        return []
    if isinstance(x, Pair):
        return [to_list_nested(x.car)] + to_list_nested(x.cdr)
    return x


def classify(x, state):
    if not isinstance(x, list):
        return
    yield x, state
    elements = dfa[state][x[0]]
    for i, el in enumerate(x[1:]):
        yield from classify(el, elements[i % len(elements)])


class DFATest(unittest.TestCase):
    def classify_elements_in_code(self, code):
        with recursionlimit(max(1500, len(code))):
            print("#" * 80)
            print(code)
            code = python_to_s_exp(code)
            print(code)
            # pylint: disable=unbalanced-tuple-unpacking
            (code,) = parse(code, ParserConfig(prefix_symbols=[], dots_are_cons=False))
            code = to_list_nested(code)
            result = sorted({(x, state) for ((x, *_), state) in classify(code, "M")})
            extras = set(result) - set(reasonable_classifications)
            if extras:
                print(sorted(extras | set(reasonable_classifications)))
                self.fail(f"Extras found in classification {extras}")

    @expand_with_slow_tests(len(small_set_examples()))
    def test_realistic(self, i):
        code = small_set_examples()[i]
        for element in ast.parse(code).body:
            self.classify_elements_in_code(ast.unparse(element))
