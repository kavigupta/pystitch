import ast
import json
import unittest
from textwrap import dedent

import neurosym as ns

from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.parser.symbol import Symbol
from imperative_stitch.utils.classify_nodes import (
    TRANSITIONS,
    classify_nodes_in_program,
    export_dfa,
)
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
    ("Raise", "S"),
    ("Return", "S"),
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
    ("list", "listE"),
    ("list", "listE_starrable"),
    ("list", "EH"),
    ("list", "listF"),
    ("list", "K"),
    ("list", "L"),
    ("list", "W"),
    ("list", "O"),
    ("list", "alias"),
    ("list", "names"),
    ("/seq", "seqS"),
    ("withitem", "W"),
]


class TestClassifications(unittest.TestCase):
    def classify_in_code(self, code, start_state):
        classified = [
            (ns.render_s_expression(x), tag)
            for x, tag in classify_nodes_in_program(
                dfa, code.to_ns_s_exp(dict()), start_state
            )
            if isinstance(x, ns.SExpression)
        ]
        print(classified)
        return classified

    def test_module_classify(self):
        self.assertEqual(
            self.classify_in_code(ParsedAST.parse_python_module("x = 2"), "M"),
            [
                (
                    "(Module (/seq (Assign (list (Name &x:0 Store)) (Constant i2 None) None)) nil)",
                    "M",
                ),
                (
                    "(/seq (Assign (list (Name &x:0 Store)) (Constant i2 None) None))",
                    "seqS",
                ),
                ("(Assign (list (Name &x:0 Store)) (Constant i2 None) None)", "S"),
                ("(list (Name &x:0 Store))", "L"),
                ("(Name &x:0 Store)", "L"),
                ("(Constant i2 None)", "E"),
            ],
        )

    def test_statement_classify(self):
        self.assertEqual(
            self.classify_in_code(ParsedAST.parse_python_statement("x = 2"), "S"),
            [
                ("(Assign (list (Name &x:0 Store)) (Constant i2 None) None)", "S"),
                ("(list (Name &x:0 Store))", "L"),
                ("(Name &x:0 Store)", "L"),
                ("(Constant i2 None)", "E"),
            ],
        )


class TestClassifications(unittest.TestCase):
    def classify_in_code(self, code, start_state):
        classified = [
            (Renderer().render(from_list_nested(x)), tag)
            for x, tag in classify_code(code, start_state, mutate=False)
        ]
        print(classified)
        return classified

    def test_module_classify(self):
        self.assertEqual(
            self.classify_in_code(ParsedAST.parse_python_module("x = 2"), "M"),
            [
                (
                    "(Module (/seq (Assign (list (Name &x:0 Store)) (Constant i2 None) None)) nil)",
                    "M",
                ),
                (
                    "(/seq (Assign (list (Name &x:0 Store)) (Constant i2 None) None))",
                    "seqS",
                ),
                ("(Assign (list (Name &x:0 Store)) (Constant i2 None) None)", "S"),
                ("(list (Name &x:0 Store))", "L"),
                ("(Name &x:0 Store)", "L"),
                ("(Constant i2 None)", "E"),
            ],
        )

    def test_statement_classify(self):
        self.assertEqual(
            self.classify_in_code(ParsedAST.parse_python_statement("x = 2"), "S"),
            [
                ("(Assign (list (Name &x:0 Store)) (Constant i2 None) None)", "S"),
                ("(list (Name &x:0 Store))", "L"),
                ("(Name &x:0 Store)", "L"),
                ("(Constant i2 None)", "E"),
            ],
        )


class DFATest(unittest.TestCase):
    def classify_elements_in_code(self, code):
        with limit_to_size(code):
            print("#" * 80)
            print(code)
            code = ParsedAST.parse_python_module(code).to_ns_s_exp(dict())
            classified = classify_nodes_in_program(dfa, code, "M")
            result = sorted(
                {
                    (x.symbol, state)
                    for (x, state) in classified
                    if isinstance(x, ns.SExpression)
                }
            )
            extras = set(result) - set(reasonable_classifications)
            if extras:
                print(sorted(extras | set(reasonable_classifications)))
                self.fail(f"Extras found in classification {extras}")

    @expand_with_slow_tests(len(small_set_examples()))
    def test_realistic(self, i):
        code = small_set_examples()[i]
        for element in ast.parse(code).body:
            self.classify_elements_in_code(ast.unparse(element))

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

    def test_for(self):
        self.classify_elements_in_code("for x in range(10): pass")

    def test_comparison(self):
        self.classify_elements_in_code("x == 2")

    def test_aug_assign(self):
        self.classify_elements_in_code("(x := 2)")

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

    def test_import(self):
        self.classify_elements_in_code("import x")
        self.classify_elements_in_code("from x import y")
        self.classify_elements_in_code("from x import y as z")

    def test_global_nonlocal(self):
        self.classify_elements_in_code("global x")
        self.classify_elements_in_code("nonlocal x")

    def test_joined_str(self):
        self.classify_elements_in_code("f'2 {459.67:.1f}'")

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
            code = ParsedAST.parse_python_module(code)
            e_nodes = [
                ns.render_s_expression(x)
                for x, state in classify_nodes_in_program(
                    dfa, code.to_ns_s_exp(dict()), "M"
                )
                if state == "E" and isinstance(x, ns.SExpression)
            ]
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

    def test_e_nodes_basic(self):
        e_nodes = self.e_nodes("x == 2")
        self.assertEqual(
            e_nodes,
            [
                "(Compare (Name g_x Load) (list Eq) (list (Constant i2 None)))",
                "(Name g_x Load)",
                "(Constant i2 None)",
            ],
        )

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
