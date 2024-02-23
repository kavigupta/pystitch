import ast
import json
import re
import unittest
from textwrap import dedent

from s_expression_parser import Pair, ParserConfig, Renderer, nil, parse

from imperative_stitch.parser import python_to_s_exp
from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.parser.symbol import Symbol
from imperative_stitch.utils.classify_nodes import TRANSITIONS, export_dfa
from imperative_stitch.utils.recursion import limit_to_size

from .utils import expand_with_slow_tests, small_set_examples

dfa = export_dfa(TRANSITIONS)

reasonable_classifications = [
    ("alias", "alias"),
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
    ("Delete", "S"),
    ("Dict", "E"),
    ("DictComp", "E"),
    *[
        (x, "O")
        for x in [
            "Add",
            "Sub",
            "Mult",
            "MatMult",
            "Div",
            "Mod",
            "Pow",
            "LShift",
            "RShift",
            "BitOr",
            "BitXor",
            "BitAnd",
            "FloorDiv",
            "Invert",
            "Not",
            "UAdd",
            "USub",
            "Eq",
            "NotEq",
            "Lt",
            "LtE",
            "Gt",
            "GtE",
            "Is",
            "IsNot",
            "In",
            "NotIn",
            "And",
            "Or",
        ]
    ],
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
    ("JoinedStr", "F"),
    ("Lambda", "E"),
    ("List", "E"),
    ("List", "L"),
    ("ListComp", "E"),
    ("Module", "M"),
    ("Name", "E"),
    ("Name", "L"),
    ("NamedExpr", "E"),
    ("Nonlocal", "S"),
    ("Pass", "S"),
    ("Raise", "S"),
    ("Return", "S"),
    ("Break", "S"),
    ("Continue", "S"),
    ("Set", "E"),
    ("SetComp", "E"),
    ("_slice_content", "SliceRoot"),
    ("_slice_slice", "SliceRoot"),
    ("_slice_tuple", "SliceRoot"),
    ("Tuple", "SliceTuple"),
    ("list", "listSliceRoot"),
    ("Slice", "Slice"),
    ("Starred", "L"),
    ("Starred", "Starred"),
    ("_starred_content", "StarredRoot"),
    ("_starred_content", "L"),
    ("_starred_starred", "StarredRoot"),
    ("_starred_starred", "L"),
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
    ("arg", "A"),
    ("arguments", "As"),
    ("comprehension", "C"),
    ("keyword", "K"),
    ("list", "A"),
    ("list", "C"),
    ("list", "[E]"),
    ("list", "listE_starrable"),
    ("list", "EH"),
    ("list", "listF"),
    ("list", "K"),
    ("list", "L"),
    ("list", "W"),
    ("list", "O"),
    ("list", "alias"),
    ("list", "names"),
    ("list", "TI"),
    ("/seq", "seqS"),
    ("withitem", "W"),
    ("const-None", "E"),
    # formatting
    ("const-None", "F"),
    ("const-s.*", "F"),
    # vararg
    ("const-None", "A"),
    # type
    (".*", "TA"),
    ("const-None", "TC"),
    # left value
    ("const-None", "L"),
    # Load/Store/Del
    ("Load", "Ctx"),
    ("Store", "Ctx"),
    ("Del", "Ctx"),
    # name
    ("const-[&g].*", "Name"),
    ("const-[&g].*", "NullableName"),
    ("const-None", "NullableName"),
    ("const-s.*", "NameStr"),
    ("const-[&g].*", "NameStr"),  # imports
    ("const-s.*", "NullableNameStr"),
    ("const-None", "NullableNameStr"),
    ("const-[&g].*", "NullableNameStr"),
    # values
    ("const-None", "Const"),
    ("const-True", "Const"),
    ("const-False", "Const"),
    ("const-Ellipsis", "Const"),
    ("const-[sbijf].*", "Const"),
    # constkind
    ("const-None", "ConstKind"),
    ("const-s.*", "ConstKind"),
    # constants
    ("const-i[01]", "bool"),
    ("const-i.*", "int"),
]


def to_list_nested(x):
    if x is nil:
        return []
    if isinstance(x, Pair):
        return [to_list_nested(x.car)] + to_list_nested(x.cdr)
    return x


def from_list_nested(x):
    if not x:
        return nil
    if not isinstance(x, list):
        return x
    return Pair(from_list_nested(x[0]), from_list_nested(x[1:]))


def classify(x, state, *, mutate):
    if not isinstance(x, list):
        return
    yield x, state
    tag = x[0]
    if mutate:
        x[0] += "::" + state
    if not x[1:]:
        return
    if tag not in dfa[state]:
        raise ValueError(f"Unknown state {tag} in {state}")
    elements = dfa[state][tag]
    for i, el in enumerate(x[1:]):
        yield from classify(el, elements[i % len(elements)], mutate=mutate)


def prep_for_classification(parsed_ast, **kwargs):
    code = parsed_ast.to_s_exp(**kwargs)
    # pylint: disable=unbalanced-tuple-unpacking
    (code,) = parse(code, ParserConfig(prefix_symbols=[], dots_are_cons=False))
    code = to_list_nested(code)
    return code


def classify_code(parsed_ast, start_state, *, mutate):
    code = prep_for_classification(parsed_ast)
    return list(classify(code, start_state, mutate=mutate))


class DFATest(unittest.TestCase):
    def check_reasonable_classification(self, tag_to_check, state_to_check):
        for tag, state in reasonable_classifications:
            mat = re.match("^" + tag + "$", tag_to_check)
            if mat and state == state_to_check:
                return
        self.fail(f"Unknown classification {tag_to_check} {state_to_check}")

    def classify_elements_in_code_with_config(self, code, **kwargs):
        with limit_to_size(code):
            print("#" * 80)
            print(code)
            code = prep_for_classification(
                ParsedAST.parse_python_module(code), **kwargs
            )
            classified = classify(code, "M", mutate=False)
            result = sorted({(x, state) for ((x, *_), state) in classified})
            list(classify(code, "M", mutate=True))
            print(code)
            for x, state in result:
                self.check_reasonable_classification(x, state)

    def classify_elements_in_code(self, code):
        self.classify_elements_in_code_with_config(code)
        self.classify_elements_in_code_with_config(code, no_leaves=True)

    @expand_with_slow_tests(len(small_set_examples()))
    def test_realistic(self, i):
        code = small_set_examples()[i]
        for element in ast.parse(code).body:
            self.classify_elements_in_code(ast.unparse(element))

    def test_function(self):
        self.classify_elements_in_code(
            dedent(
                """
                def f(x):
                    pass
                """
            )
        )
        self.classify_elements_in_code(
            dedent(
                """
                def f(x, *y, z=2, **w):
                    pass
                """
            )
        )

    def test_with(self):
        self.classify_elements_in_code(
            dedent(
                """
                with x:
                    pass
                """
            )
        )

    def test_annotation(self):
        self.classify_elements_in_code(
            dedent(
                """
                @asyncio.coroutine
                def onOpen(self):
                    pass
                """
            )
        )

    def test_class(self):
        self.classify_elements_in_code(
            dedent(
                """
                class MyClientProtocol(WebSocketClientProtocol):
                    pass
                """
            )
        )

    def test_exception(self):
        self.classify_elements_in_code(
            dedent(
                """
                try:
                    x = 2
                except:
                    pass
                """
            )
        )

    def test_comparison(self):
        self.classify_elements_in_code("x == 2")

    def test_keyword(self):
        self.classify_elements_in_code("f(x=2)")

    def test_aug_assign(self):
        self.classify_elements_in_code("(x := 2)")

    def test_assign(self):
        self.classify_elements_in_code("x = 2")
        self.classify_elements_in_code("x = 2, 3")
        self.classify_elements_in_code("x += 2")

    def test_tuple(self):
        self.classify_elements_in_code("(2, 3)")

    def test_unpacking(self):
        self.classify_elements_in_code("a, b = 1, 2")
        self.classify_elements_in_code("a, *b = 1, 2, 3")
        self.classify_elements_in_code("[a, b] = 1, 2, 3")

    def test_slicing_direct(self):
        self.classify_elements_in_code("x[2]")
        self.classify_elements_in_code("x[2:3]")
        self.classify_elements_in_code("x[2:3] = 4")

    def test_slicing_tuple(self):
        self.classify_elements_in_code("x[2:3, 3]")
        self.classify_elements_in_code("x[2:3, 3] = 5")

    def test_starred(self):
        self.classify_elements_in_code("f(2, 3, *x)")
        self.classify_elements_in_code("(2, 3, *x)")
        self.classify_elements_in_code("[2, 3, *x]")
        self.classify_elements_in_code("{2, 3, *x}")

    def test_kwstarred(self):
        self.classify_elements_in_code("f(2, 3, **x)")

    def test_import(self):
        self.classify_elements_in_code("import x")
        self.classify_elements_in_code("from x import y")
        self.classify_elements_in_code("from x import y as z")
        self.classify_elements_in_code("from . import x")

    def test_global_nonlocal(self):
        self.classify_elements_in_code("global x")
        self.classify_elements_in_code("nonlocal x")

    def test_joined_str(self):
        self.classify_elements_in_code("f'2 {459.67:.1f}'")

    def test_type_annotation(self):
        self.classify_elements_in_code("x: int = 2")
        self.classify_elements_in_code("def f(x: int) -> int: pass")
        self.classify_elements_in_code("x: List[int] = []")

    def test_code(self):
        self.classify_elements_in_code(
            dedent(
                r"""
                {x: 2 for x in range(10)}
                """
            )
        )


class TestExprNodeValidity(unittest.TestCase):
    def e_nodes(self, code):
        with limit_to_size(code):
            print("#" * 80)
            print(code)
            code = python_to_s_exp(code)
            print(code)
            # pylint: disable=unbalanced-tuple-unpacking
            (code,) = parse(code, ParserConfig(prefix_symbols=[], dots_are_cons=False))
            code = to_list_nested(code)
            e_nodes = [
                x for x, state in classify(code, "M", mutate=False) if state == "E"
            ]
            e_nodes = [Renderer().render(from_list_nested(x)) for x in e_nodes]
            return e_nodes

    def assertENodeReal(self, node):
        print(node)
        code = ParsedAST.parse_s_expression(node)
        print(code)
        code_in_function_call = ParsedAST.call(Symbol(name="hi", scope=None), code)
        code_in_function_call = code_in_function_call.to_python()
        print(code_in_function_call)
        code_in_function_call = ParsedAST.parse_python_statement(code_in_function_call)
        assert code_in_function_call.typ == ast.Expr
        code_in_function_call = code_in_function_call.children[0]
        assert code_in_function_call.typ == ast.Call
        code_in_function_call = code_in_function_call.children[1]
        code_in_function_call = code_in_function_call.children[0].content
        print(code_in_function_call)
        code_in_function_call = code_in_function_call.to_python()
        print(code_in_function_call)
        self.maxDiff = None
        self.assertEqual(code.to_python(), code_in_function_call)

    def assertENodesReal(self, code):
        e_nodes = self.e_nodes(code)
        for node in e_nodes:
            self.assertENodeReal(node)

    def test_slice(self):
        self.assertENodesReal("y = x[2:3]")

    @expand_with_slow_tests(len(small_set_examples()))
    def test_realistic(self, i):
        code = small_set_examples()[i]
        for element in ast.parse(code).body:
            self.assertENodesReal(ast.unparse(element))

    def test_dfa_file(self):
        self.maxDiff = None

        with open("data/dfa.json") as f:
            x = json.load(f)

        self.assertEqual(export_dfa(), x)
