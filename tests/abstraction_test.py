import unittest
from textwrap import dedent

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl


def assertSameCode(test, actual, expected):
    print(actual)
    test.assertEqual(
        dedent(actual).strip(),
        dedent(expected).strip(),
    )


class AbstractionRenderingTest(unittest.TestCase):
    fn_1_body = """
    (/subseq
        (Assign (list (Name %1 Store)) (Call (Name g_int Load) (list (Call (Name g_input Load) nil nil)) nil) None)
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
                (/seq (Expr (Call (Name g_print Load) (list (UnaryOp USub (Constant i1 None))) nil)))
                (/seq (Expr (Call (Name g_print Load) (list (Constant i0 None)) nil)))
                )
            )
            (/seq
                (Expr (Call (Name g_print Load) (list (Constant i1 None)) nil))
                (Expr (Call (Name g_print Load) (list (BinOp (UnaryOp USub (Name %1 Load)) Div (Name %3 Load))) nil))
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
            (Expr #0)
            (/seq
                (If
                (Compare (Name %4 Load) (list Eq) (list (Constant i0 None)))
                (/seq
                    (Expr (Call (Name g_print Load) (list (Constant i1 None)) nil))
                    (Expr
                    (Call
                        (Name g_print Load)
                        (list (BinOp (UnaryOp USub (Name %3 Load)) Div (BinOp (Constant i2 None) Mult (Name %2 Load))))
                        nil
                    )
                    )
                )
                (/seq (Expr (Call (Name g_print Load) (list (Constant i0 None)) nil)))
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

    def test_stub_rendering_simple(self):
        stub = self.fn_1.create_stub(self.fn_1_args)
        assertSameCode(
            self,
            stub.to_python(),
            """
            fn_1(__ref__(a), __ref__(z))
            """,
        )

    def test_stub_rendering_multi(self):
        stub = self.fn_2.create_stub(self.fn_2_args)
        assertSameCode(
            self,
            stub.to_python(),
            """
            fn_2(__code__('print(2)'), __ref__(c), __ref__(a), __ref__(b), __ref__(d), __code__('if x == 3:\\n    pass'))
            """,
        )

    def test_stub_rendering_multi_w_nothing(self):
        stub = self.fn_2.create_stub(self.fn_2_args_w_nothing)
        assertSameCode(
            self,
            stub.to_python(),
            """
            fn_2(__code__('print(2)'), __ref__(c), __ref__(a), __ref__(b), __ref__(d), __code__(''))
            """,
        )

    def test_body_rendering_simple(self):
        stub = self.fn_1.substitute_body(self.fn_1_args)
        assertSameCode(
            self,
            stub.to_python(),
            """
            a = int(input())
            z = input()
            """,
        )

    def test_body_rendering_simple_with_pragmas(self):
        stub = self.fn_1.substitute_body(self.fn_1_args, pragmas=True)
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
        stub = self.fn_2.substitute_body(self.fn_2_args)
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
        stub = self.fn_2.substitute_body(self.fn_2_args, pragmas=True)
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
        stub = self.fn_2.substitute_body(self.fn_2_args_w_nothing)
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
        body = self.fn_1.body_with_variable_names()
        assertSameCode(
            self,
            body.to_python(),
            """
            %1 = int(input())
            %2 = input()
            """,
        )

    def test_body_variable_rendering_multi(self):
        body = self.fn_2.body_with_variable_names()
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

    def test_dfa_with_abstractions_works(self):
        export_dfa(abstrs={"fn_1": self.fn_1, "fn_2": self.fn_2})

    def test_dsl_with_abstractions_works(self):
        dfa = export_dfa(abstrs={"fn_1": self.fn_1, "fn_2": self.fn_2})
        subset = DSLSubset.from_program(
            dfa,
            ParsedAST.parse_python_module("x = x + 2; y = y + x + 2"),
            root="M",
        )
        create_dsl(dfa, subset, "M")
