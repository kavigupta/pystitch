import unittest
from textwrap import dedent
from parameterized import parameterized

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.data.stitch_output_set import load_stitch_output_set
from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.def_use_mask.ordering import (
    python_node_dictionary,
    python_node_ordering_with_abstractions,
)
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl

fn_1_body = """
(/subseq
    (Assign
        (list (Name %1 Store))
        (Call (Name g_int Load) (list (_starred_content (Call (Name g_input Load) nil nil))) nil) None)
    (Assign (list (Name %2 Store)) (Call (Name g_input Load) nil nil) None))
"""

fn_1 = Abstraction(
    name="fn_1",
    body=ParsedAST.parse_s_expression(fn_1_body),
    arity=0,
    sym_arity=2,
    choice_arity=0,
    dfa_root="seqS",
    dfa_symvars=["X", "X"],
    dfa_metavars=[],
    dfa_choicevars=[],
)

fn_1_args = [ParsedAST.parse_s_expression(x) for x in ["&a:0", "&z:0"]]

fn_2_body = """
(If
    (Compare (Name %2 Load) (list Eq) (list (Constant i0 None)))
    (/seq
        (If
        (Compare (Name %3 Load) (list Eq) (list (Constant i0 None)))
        (/seq
            (If
            (Compare (Name %1 Load) (list Eq) (list (Constant i0 None)))
            (/seq (Expr (Call (Name g_print Load) (list (_starred_content (UnaryOp USub (Constant i1 None)))) nil)))
            (/seq (Expr (Call (Name g_print Load) (list (_starred_content (Constant i0 None))) nil)))
            )
        )
        (/seq
            (Expr (Call (Name g_print Load) (list (_starred_content (Constant i1 None))) nil))
            (Expr (Call (Name g_print Load) (list (_starred_content (BinOp (UnaryOp USub (Name %1 Load)) Div (Name %3 Load)))) nil))
        )
        )
    )
    (/seq
        ?0
        (Assign
        (list (Name %4 Store))
        (BinOp
            (BinOp (Name %3 Load) Pow (Constant i2 None))
            Sub
            (BinOp (BinOp (Constant i4 None) Mult (Name %2 Load)) Mult (Name %1 Load))
        )
        None
        )
        (If
        (Compare (Name %4 Load) (list Gt) (list (Constant i0 None)))
        (/seq (Expr #0))
        (/seq
            (If
            (Compare (Name %4 Load) (list Eq) (list (Constant i0 None)))
            (/seq
                (Expr (Call (Name g_print Load) (list (_starred_content (Constant i1 None))) nil))
                (Expr
                (Call
                    (Name g_print Load)
                    (list (_starred_content (BinOp (UnaryOp USub (Name %3 Load)) Div (BinOp (Constant i2 None) Mult (Name %2 Load)))))
                    nil
                )
                )
            )
            (/seq (Expr (Call (Name g_print Load) (list (_starred_content (Constant i0 None))) nil)))
            )
        )
        )
    )
)
"""

fn_2 = Abstraction(
    name="fn_2",
    body=ParsedAST.parse_s_expression(fn_2_body),
    arity=1,
    sym_arity=4,
    choice_arity=1,
    dfa_root="S",
    dfa_symvars=["X", "X", "X", "X"],
    dfa_metavars=["E"],
    dfa_choicevars=["seqS"],
)

fn_2_args_w_nothing = [
    ParsedAST.parse_s_expression(x)
    for x in [
        "(Call (Name g_print Load) (list (Constant i2 None)) nil)",
        "&c:0",
        "&a:0",
        "&b:0",
        "&d:0",
        "(/choiceseq)",
    ]
]
fn_2_args = fn_2_args_w_nothing[:-1] + [
    ParsedAST.parse_python_statements("if x == 3: pass")
]


def assertSameCode(test, actual, expected):
    print(actual)
    test.assertEqual(
        dedent(actual).strip(),
        dedent(expected).strip(),
    )


class AbstractionRenderingTest(unittest.TestCase):
    def test_stub_rendering_simple(self):
        stub = fn_1.create_stub(fn_1_args)
        assertSameCode(
            self,
            stub.to_python(),
            """
            fn_1(__ref__(a), __ref__(z))
            """,
        )

    def test_stub_rendering_multi(self):
        stub = fn_2.create_stub(fn_2_args)
        assertSameCode(
            self,
            stub.to_python(),
            """
            fn_2(__code__('print(2)'), __ref__(c), __ref__(a), __ref__(b), __ref__(d), __code__('if x == 3:\\n    pass'))
            """,
        )

    def test_stub_rendering_multi_w_nothing(self):
        stub = fn_2.create_stub(fn_2_args_w_nothing)
        assertSameCode(
            self,
            stub.to_python(),
            """
            fn_2(__code__('print(2)'), __ref__(c), __ref__(a), __ref__(b), __ref__(d), __code__(''))
            """,
        )

    def test_body_rendering_simple(self):
        stub = fn_1.substitute_body(fn_1_args)
        assertSameCode(
            self,
            stub.to_python(),
            """
            a = int(input())
            z = input()
            """,
        )

    def test_body_rendering_simple_with_pragmas(self):
        stub = fn_1.substitute_body(fn_1_args, pragmas=True)
        assertSameCode(
            self,
            stub.to_python(),
            """
            __start_extract__
            a = int(input())
            z = input()
            __end_extract__
            """,
        )

    def test_body_rendering_multi(self):
        stub = fn_2.substitute_body(fn_2_args)
        print(stub.to_python())
        assertSameCode(
            self,
            stub.to_python(),
            """
            if a == 0:
                if b == 0:
                    if c == 0:
                        print(-1)
                    else:
                        print(0)
                else:
                    print(1)
                    print(-c / b)
            else:
                if x == 3:
                    pass
                d = b ** 2 - 4 * a * c
                if d > 0:
                    print(2)
                elif d == 0:
                    print(1)
                    print(-b / (2 * a))
                else:
                    print(0)
            """,
        )

    def test_body_rendering_multi_with_pragmas(self):
        stub = fn_2.substitute_body(fn_2_args, pragmas=True)
        print(stub.to_python())
        assertSameCode(
            self,
            stub.to_python(),
            """
            __start_extract__
            if a == 0:
                if b == 0:
                    if c == 0:
                        print(-1)
                    else:
                        print(0)
                else:
                    print(1)
                    print(-c / b)
            else:
                __start_choice__
                if x == 3:
                    pass
                __end_choice__
                d = b ** 2 - 4 * a * c
                if d > 0:
                    {__metavariable__, __m0, print(2)}
                elif d == 0:
                    print(1)
                    print(-b / (2 * a))
                else:
                    print(0)
            __end_extract__
            """,
        )

    def test_body_rendering_multi_w_nothing(self):
        stub = fn_2.substitute_body(fn_2_args_w_nothing)
        assertSameCode(
            self,
            stub.to_python(),
            """
            if a == 0:
                if b == 0:
                    if c == 0:
                        print(-1)
                    else:
                        print(0)
                else:
                    print(1)
                    print(-c / b)
            else:
                d = b ** 2 - 4 * a * c
                if d > 0:
                    print(2)
                elif d == 0:
                    print(1)
                    print(-b / (2 * a))
                else:
                    print(0)
            """,
        )

    def test_body_variable_rendering_simple(self):
        body = fn_1.body_with_variable_names()
        assertSameCode(
            self,
            body.to_python(),
            """
            %1 = int(input())
            %2 = input()
            """,
        )

    def test_body_variable_rendering_multi(self):
        body = fn_2.body_with_variable_names()
        self.maxDiff = None
        assertSameCode(
            self,
            body.to_python(),
            """
            if %2 == 0:
                if %3 == 0:
                    if %1 == 0:
                        print(-1)
                    else:
                        print(0)
                else:
                    print(1)
                    print(-%1 / %3)
            else:
                ?0
                %4 = %3 ** 2 - 4 * %2 * %1
                if %4 > 0:
                    #0
                elif %4 == 0:
                    print(1)
                    print(-%3 / (2 * %2))
                else:
                    print(0)
            """,
        )

    def test_nested_abstraction_render(self):
        fn_5_init = {
            "body": ParsedAST.parse_s_expression(
                """
                (/subseq
                    (While
                        (Name %2 Load)
                        (/seq
                            (AugAssign
                                (Name %3 Store)
                                Add
                                (BinOp (Name %2 Load) Mod (Name %1 Load)))
                            (AugAssign (Name %2 Store) FloorDiv (Name %1 Load))
                            ?0)
                        (/seq))
                    (If
                        (Compare
                            (Name %3 Load) (list Eq) (list (Name %4 Load)))
                        (/seq (Return (Name %1 Load)))
                        (/seq)))
                """
            ),
            "sym_arity": 4,
            "dfa_symvars": ["Name", "Name", "Name", "Name"],
            "dfa_metavars": [],
            "dfa_choicevars": ["seqS"],
            "choice_arity": 1,
            "arity": 0,
            "dfa_root": "seqS",
        }

        fn_5 = Abstraction(name="fn_5", **fn_5_init)
        tmp_abstraction_calls = {"fn_5": fn_5}
        result = (
            ParsedAST.parse_s_expression("(/splice (fn_5 %1 %4 %5 %2 #0))")
            .abstraction_calls_to_bodies(tmp_abstraction_calls)
            .to_s_exp()
        )
        expected = """
        (/splice
            (/subseq
                (While
                    (Name %4 Load)
                    (/seq
                        (AugAssign
                            (Name %5 Store)
                            Add
                            (BinOp (Name %4 Load) Mod (Name %1 Load)))
                        (AugAssign (Name %4 Store) FloorDiv (Name %1 Load))
                        (/splice #0))
                        (/seq))
                    (If
                        (Compare (Name %5 Load) (list Eq) (list (Name %2 Load)))
                        (/seq (Return (Name %1 Load))) (/seq))))
        """
        expected = ParsedAST.parse_s_expression(expected).to_s_exp()
        self.assertEqual(result, expected)

    def test_dfa_with_abstractions_works(self):
        export_dfa(abstrs={"fn_1": fn_1, "fn_2": fn_2})

    def test_dsl_with_abstractions_works(self):
        dfa = export_dfa(abstrs={"fn_1": fn_1, "fn_2": fn_2})
        subset = DSLSubset.from_program(
            dfa,
            ParsedAST.parse_python_module("x = x + 2; y = y + x + 2"),
            root="M",
        )
        create_dsl(dfa, subset, "M")

    def test_in_order_simple(self):
        self.assertEqual(
            fn_1.variables_in_order(python_node_dictionary()), ["%1", "%2"]
        )
        self.assertEqual(
            fn_1.arguments_traversal_order(python_node_dictionary()), [0, 1]
        )

    def test_in_order_multi(self):
        self.assertEqual(
            fn_2.variables_in_order(python_node_dictionary()),
            ["%2", "%3", "%1", "?0", "%4", "#0"],
        )
        # order is #0 %1 %2 %3 %4 ?0
        self.assertEqual(
            fn_2.arguments_traversal_order(python_node_dictionary()), [2, 3, 1, 5, 4, 0]
        )

    def test_in_order_comprehension(self):
        fn_3 = Abstraction(
            name="fn_3",
            body=ParsedAST.parse_s_expression(
                """
                (Expr
                    (ListComp
                        #0
                        (list
                            (comprehension
                                (Name %1 Store)
                                (Call 
                                    #1
                                    (list (_starred_content (Constant i10 None))) 
                                    nil)
                                nil
                                i0))))
                """
            ),
            arity=2,
            sym_arity=1,
            choice_arity=0,
            dfa_root="S",
            dfa_symvars=["Name"],
            dfa_metavars=["E", "E"],
            dfa_choicevars=[],
        )
        self.assertEqual(
            fn_3.variables_in_order(python_node_dictionary()), ["%1", "#1", "#0"]
        )

    @parameterized.expand(range(len(load_stitch_output_set())))
    def test_abstraction_bodies_in_order_no_crash(self, i):
        x = load_stitch_output_set()[i]
        abstractions = []
        for idx, abstraction in enumerate(x["abstractions"], 1):
            abstraction["body"] = ParsedAST.parse_s_expression(abstraction["body"])
            abstraction = Abstraction(**abstraction, name=f"fn_{idx}")
            abstractions.append(abstraction)
        python_node_ordering_with_abstractions(abstractions)
