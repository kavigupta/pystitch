import ast
import copy
import sys
import unittest

import neurosym as ns

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.data.stitch_output_set import load_stitch_output_set
from imperative_stitch.parser.parsed_ast import NodeAST, ParsedAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.def_use_mask.mask import DefUseChainPreorderMask
from imperative_stitch.utils.def_use_mask.names import match_either
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl
from tests.dsl_tests.dsl_test import fit_to
from tests.utils import cwq, expand_with_slow_tests, small_set_runnable_code_examples


class DefUseMaskTestGeneric(unittest.TestCase):
    def annotate_alternates(self, chosen, alts):
        self.assertIn(chosen, alts)
        mat = match_either(chosen)
        if not mat:
            return chosen
        name, scope = mat.group("name"), (
            mat.group("scope") if mat.group("typ") == "&" else "0"
        )
        # print(alts)
        alts = [match_either(alt) for alt in alts]
        # print([x for x in alts if x])
        alts = {x.group("name") for x in alts if x}
        alts.remove(name)
        alts = sorted(alts)
        if alts:
            name = f"{name}?{'$'.join(alts)}"
        return f"const-&{name}:{scope}~Name"

    def annotate_program(
        self, program, parser=ParsedAST.parse_python_module, abstrs=()
    ):
        dfa, _, fam, _ = fit_to([program], parser=parser, abstrs=abstrs)
        annotated = ParsedAST.parse_s_expression(
            ns.render_s_expression(
                ns.annotate_with_alternate_symbols(
                    parser(program).to_type_annotated_ns_s_exp(dfa, "M"),
                    fam.tree_distribution_skeleton,
                    self.annotate_alternates,
                )
            )
        )
        annotated = annotated.abstraction_calls_to_stubs({x.name: x for x in abstrs})
        return annotated.to_python()


class DefUseMaskTest(DefUseMaskTestGeneric):
    def test_annotate_alternate_symbols(self):
        code = self.annotate_program("x = 2; y = x; z = y")
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                x?y$z = 2
                y?x$z = x
                z?x$y = y?x
                """
            ).strip(),
        )

    def test_subscript_on_lhs(self):
        code = self.annotate_program("x = [2, 3, 4]; x[2] = x[0]; y = 2")
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                x?y = [2, 3, 4]
                x[2] = x[0]
                y?x = 2
                """
            ).strip(),
        )

    def test_attribute_on_lhs(self):
        code = self.annotate_program("x = 2; y.z = 3; x = x")
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                x?y = 2
                y?x.z = 3
                x?y = x?y
                """
            ).strip(),
        )

    def test_tuple_list_on_lhs(self):
        code = self.annotate_program("[x, y] = 2, 3; x, y = x, y; z = x")
        print(code)
        past_310 = """
        [x?y$z, y?x$z] = (2, 3)
        x?y$z, y?x$z = (x?y, y?x)
        z?x$y = x?y
        """
        up_to_310 = """
        [x?y$z, y?x$z] = (2, 3)
        (x?y$z, y?x$z) = (x?y, y?x)
        z?x$y = x?y
        """
        self.assertEqual(
            code.strip(),
            cwq(up_to_310 if sys.version_info < (3, 11) else past_310).strip(),
        )

    def test_star_tuple_on_lhs(self):
        code = self.annotate_program("x, *y = [2, 3]; x = x")
        print(code)
        past_310 = """
        x?y, *y?x = [2, 3]
        x?y = x?y
        """
        up_to_310 = """
        (x?y, *y?x) = [2, 3]
        x?y = x?y
        """
        self.assertEqual(
            code.strip(),
            cwq(up_to_310 if sys.version_info < (3, 11) else past_310).strip(),
        )

    def test_basic_import(self):
        # the 2 in front is necessary to force the import to not be pulled
        code = self.annotate_program(
            cwq(
                """
                2
                import os
                import sys as y
                from collections import defaultdict
                from collections import defaultdict as z
                x = os
                x = os
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                2
                import os?defaultdict$x$y$z
                import sys as y?defaultdict$os$x$z
                from collections import defaultdict?os$x$y$z
                from collections import defaultdict as z?defaultdict$os$x$y
                x?defaultdict$os$y$z = os?defaultdict$y$z
                x?defaultdict$os$y$z = os?defaultdict$x$y$z
                """
            ).strip(),
        )

    def test_function_call(self):
        code = self.annotate_program(
            cwq(
                """
                def f(x):
                    z = x
                    return x
                y = f(2)
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                def f?x$y$z(x?f$y$z):
                    z?f$x$y = x?f
                    return x?f$z
                y?f$x$z = f(2)
                """
            ).strip(),
        )

    def test_lambda(self):
        code = self.annotate_program(
            cwq(
                """
                x = 2
                lambda y, z=x: lambda a=y: x
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                x?a$y$z = 2
                lambda y?a$x$z, z?a$x$y=x: lambda a?x$y$z=y?x$z: x?a$y$z
                """
            ).strip(),
        )

    def test_function_call_arguments(self):
        code = self.annotate_program(
            cwq(
                """
                def f(w, /, x, *y, **z):
                    return x
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                def f?w$x$y$z(w?f$x$y$z, /, x?f$w$y$z, *y?f$w$x$z, **z?f$w$x$y):
                    return x?f$w$y$z
                """
            ).strip(),
        )

    def test_single_comprehension(self):
        code = self.annotate_program(
            cwq(
                """
                a = 2
                [b for b in range(a) if b == a]
                a = a
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                a?b$range = 2
                [b?a$range for b?a$range in range?a(a?range) if b?a$range == a?b$range]
                a?b$range = a?range
                """
            ).strip(),
        )

    def test_bunch_of_comprehensions(self):
        self.maxDiff = None
        code = self.annotate_program(
            cwq(
                """
                a = 2
                [b for b in range(a)]
                (c for c in range(a))
                {c for c in range(a)}
                {d: a for d in range(a)}
                [e + f + g for e in range(a) for f in range(e) for g in range(f)]
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                a?b$c$d$e$f$g$range = 2
                [b?a$range for b?a$c$d$e$f$g$range in range?a(a?range)]
                (c?a$range for c?a$b$d$e$f$g$range in range?a(a?range))
                {c?a$range for c?a$b$d$e$f$g$range in range?a(a?range)}
                {d?a$range: a?d$range for d?a$b$c$e$f$g$range in range?a(a?range)}
                [e?a$f$g$range + f?a$e$g$range + g?a$e$f$range
                    for e?a$b$c$d$f$g$range in range?a(a?range)
                    for f?a$b$c$d$e$g$range in range?a$e(e?a$range)
                    for g?a$b$c$d$e$f$range in range?a$e$f(f?a$e$range)]
                """
            ).strip(),
        )

    def test_for(self):
        self.maxDiff = None
        code = self.annotate_program(
            cwq(
                """
                x = [2]
                for y in x:
                    y
                z = x
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                x?y$z = [2]
                for y?x$z in x:
                    y?x
                z?x$y = x?y
                """
            ).strip(),
        )

    def test_import_at_top_level(self):
        # imports at top are global so not alternated
        code = self.annotate_program("import os; import sys as y; x = os; x = os")
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                import os?x$y
                import sys as y?os$x
                x?os$y = os?y
                x?os$y = os?x$y
                """
            ).strip(),
        )

    def test_class(self):
        code = self.annotate_program(
            cwq(
                """
                class A:
                    x = A
                y = A
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                class A?x$y:
                    x?A$y = A
                y?A$x = A
                """
            ).strip(),
        )

    def test_import_inside_fn(self):
        code = self.annotate_program(
            cwq(
                """
                def f():
                    from collections import defaultdict
                    return defaultdict
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                def f?defaultdict():
                    from collections import defaultdict?f
                    return defaultdict?f
                """
            ).strip(),
        )

    def test_function_default(self):
        code = self.annotate_program(
            cwq(
                """
                y = 2
                z = 3
                def f(x=y):
                    return x
                z = z
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                y?f$x$z = 2
                z?f$x$y = 3

                def f?x$y$z(x?f$y$z=y?f$z):
                    return x?f$y$z
                z?f$x$y = z?f$y
                """
            ).strip(),
        )

    @expand_with_slow_tests(1000, -1)
    def test_realistic(self, i):
        if i in {22, 31, 41, 57}:
            # forward declaration of input for 22/41, n for 31/57
            return
        example = small_set_runnable_code_examples()[i]["solution"]
        print(example)
        code = self.annotate_program(example)
        print(code)


class DefUseMaskWithAbstractionsTest(DefUseMaskTestGeneric):
    def replace_s_expr(self, s_expr):
        if not isinstance(s_expr, NodeAST):
            return s_expr
        if s_expr.typ != ast.Expr:
            return s_expr
        [const] = s_expr.children
        if const.typ != ast.Constant:
            return s_expr
        leaf, _ = const.children
        leaf = leaf.leaf
        if not leaf.startswith("~"):
            return s_expr
        leaf = leaf[1:]
        return ParsedAST.parse_s_expression(leaf)

    def parse_with_hijacking(self, code):
        return ParsedAST.parse_python_module(code).map(self.replace_s_expr)

    def blank_abstraction(self, name, content):
        return Abstraction(
            name=name,
            body=ParsedAST.parse_python_statements(content),
            arity=0,
            sym_arity=0,
            choice_arity=0,
            dfa_root="seqS",
            dfa_symvars=[],
            dfa_metavars=[],
            dfa_choicevars=[],
        )

    def test_with_empty_abstraction(self):
        code = cwq(
            """
            u = 2
            k = u.count()
            "~(/splice (fn_1))"
            k = u.count()
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[self.blank_abstraction("fn_1", "a = int(input()); z = input()")],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                u?a$input$int$k$z = 2
                k?a$input$int$u$z = u?input$int.count()
                fn_1()
                k?a$input$int$u$z = u?a$input$int$k$z.count()
                """
            ).strip(),
        )

    def test_with_empty_abstraction_multi(self):
        code = cwq(
            """
            u = 2
            k = u.count()
            "~(/splice (fn_1))"
            k = u.count()
            "~(/splice (fn_2))"
            k = u.count()
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[
                self.blank_abstraction("fn_1", "a = int(input()); z = input()"),
                self.blank_abstraction("fn_2", "x = 3"),
            ],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                u?a$input$int$k$x$z = 2
                k?a$input$int$u$x$z = u?input$int.count()
                fn_1()
                k?a$input$int$u$x$z = u?a$input$int$k$z.count()
                fn_2()
                k?a$input$int$u$x$z = u?a$input$int$k$x$z.count()
                """
            ).strip(),
        )

    def test_with_symvars_ordered(self):
        code = cwq(
            """
            b = 2
            "~(fn_1 &a:0 &b:0)"
            a = a
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[
                Abstraction(
                    name="fn_1",
                    body=ParsedAST.parse_s_expression(
                        "(Assign (list (Name %1 Store)) (Name %2 Load) None)"
                    ),
                    arity=0,
                    sym_arity=2,
                    choice_arity=0,
                    dfa_root="S",
                    dfa_symvars=["Name"] * 2,
                    dfa_metavars=[],
                    dfa_choicevars=[],
                )
            ],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                b?a = 2
                # a?b = b
                fn_1(__ref__(a?b), __ref__(b))
                a?b = a?b
                """
            ).strip(),
        )

    def test_with_symvars_backwards(self):
        code = cwq(
            """
            b = 2
            "~(fn_1 &b:0 &a:0)"
            a = a
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[
                Abstraction(
                    name="fn_1",
                    body=ParsedAST.parse_s_expression(
                        "(Assign (list (Name %2 Store)) (Name %1 Load) None)"
                    ),
                    arity=0,
                    sym_arity=2,
                    choice_arity=0,
                    dfa_root="S",
                    dfa_symvars=["Name"] * 2,
                    dfa_metavars=[],
                    dfa_choicevars=[],
                )
            ],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                b?a = 2
                # a?b = b
                fn_1(__ref__(b), __ref__(a?b))
                a?b = a?b
                """
            ).strip(),
        )

    def test_with_metavariable_very_simple(self):
        code = cwq(
            """
            b = 2
            "~(fn_1 (Name &b:0 Load) &a:0)"
            a = a
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[
                Abstraction(
                    name="fn_1",
                    body=ParsedAST.parse_s_expression(
                        "(Assign (list (Name %1 Store)) #0 None)"
                    ),
                    arity=1,
                    sym_arity=1,
                    choice_arity=0,
                    dfa_root="S",
                    dfa_symvars=["Name"],
                    dfa_metavars=["E"],
                    dfa_choicevars=[],
                )
            ],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                b?a = 2
                # a?b = b
                fn_1(__code__('b'), __ref__(a?b))
                a?b = a?b
                """
            ).strip(),
        )

    def test_symvar_reuse(self):
        code = cwq(
            """
            b = 2
            "~(/splice (fn_1 &b:0 &a:0))"
            a = a
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[
                Abstraction(
                    name="fn_1",
                    body=ParsedAST.parse_s_expression(
                        "(/seq (Assign (list (Name %2 Store)) (Name %1 Load) None) (Assign (list (Name %2 Store)) (Name %1 Load) None))"
                    ),
                    arity=0,
                    sym_arity=2,
                    choice_arity=0,
                    dfa_root="seqS",
                    dfa_symvars=["Name"] * 2,
                    dfa_metavars=[],
                    dfa_choicevars=[],
                )
            ],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                b?a = 2
                # a?b = b
                fn_1(__ref__(b), __ref__(a?b))
                a?b = a?b
                """
            ).strip(),
        )

    def test_symvar_used_in_metavariable(self):
        code = cwq(
            """
            b = 2
            "~(/splice (fn_1 (Name &a:0 Load) &b:0 &a:0))"
            a = a
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[
                Abstraction(
                    name="fn_1",
                    body=ParsedAST.parse_s_expression(
                        "(/seq (Assign (list (Name %2 Store)) (Name %1 Load) None) (Assign (list (Name %2 Store)) #0 None))"
                    ),
                    arity=1,
                    sym_arity=2,
                    choice_arity=0,
                    dfa_root="seqS",
                    dfa_symvars=["Name"] * 2,
                    dfa_metavars=["E"],
                    dfa_choicevars=[],
                )
            ],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                b?a = 2
                # a?b = b
                # a?b = a?b
                fn_1(__code__('a?b'), __ref__(b), __ref__(a?b))
                a?b = a?b
                """
            ).strip(),
        )

    def test_definition_in_metavar(self):
        code = cwq(
            """
            b = 2
            "~(/splice (fn_1 (Assign (list (Name &c:0 Store)) (Name &b:0 Load) None) &c:0 &a:0))"
            a = a
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[
                Abstraction(
                    name="fn_1",
                    body=ParsedAST.parse_s_expression(
                        "(/seq #0 (Assign (list (Name %2 Store)) (Name %1 Load) None))"
                    ),
                    arity=1,
                    sym_arity=2,
                    choice_arity=0,
                    dfa_root="seqS",
                    dfa_symvars=["Name"] * 2,
                    dfa_metavars=["S"],
                    dfa_choicevars=[],
                )
            ],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                b?a$c = 2
                # c?a$b = b
                # a?b$c = c?b
                fn_1(__code__('c?a$b = b'), __ref__(c?b), __ref__(a?b$c))
                a?b$c = a?b$c
                """
            ).strip(),
        )

    def test_out_of_order_within_abstraction(self):
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
        code = cwq(
            """
            "~(fn_3 (Name &x:0 Load) (Constant i2 None) &x:0)"
            x = 2
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[fn_3],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                fn_3(__code__('x'), __code__('2'), __ref__(x))
                x = 2
                """
            ).strip(),
        )

    def test_metavar_containing_abstraction(self):
        code = cwq(
            """
            b = 2
            "~(fn_2 (fn_1) &a:0)"
            a = a
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[
                Abstraction(
                    name="fn_1",
                    body=ParsedAST.parse_s_expression("(Name &b:0 Load)"),
                    arity=0,
                    sym_arity=0,
                    choice_arity=0,
                    dfa_root="E",
                    dfa_symvars=[],
                    dfa_metavars=[],
                    dfa_choicevars=[],
                ),
                Abstraction(
                    name="fn_2",
                    body=ParsedAST.parse_s_expression(
                        "(Assign (list (Name %1 Store)) #0 None)"
                    ),
                    arity=1,
                    sym_arity=1,
                    choice_arity=0,
                    dfa_root="S",
                    dfa_symvars=["Name"],
                    dfa_metavars=["E"],
                    dfa_choicevars=[],
                ),
            ],
        )
        print(annotated)
        self.assertEqual(
            cwq(annotated).strip(),
            cwq(
                """
                b?a = 2
                # a?b = b
                fn_2(__code__('fn_1()'), __ref__(a?b))
                a?b = a?b
                """
            ).strip(),
        )

    def test_nested_generator_from_annie(self):
        stitch_abstrs = [
            {
                "body": "(/subseq (If (Compare (Name %1 Load) (list Eq) (list (Name %2 Load))) (/seq (Return (BinOp (Name %1 Load) Add (Constant i1 None)))) (/seq)) (For (Name %3 Store) (Call (Name g_range Load) (list (_starred_content (Constant i2 None)) (_starred_content (BinOp (Call (Name g_int Load) (list (_starred_content (BinOp (Name %1 Load) Pow (Constant f0.5 None)))) nil) Add (Constant i1 None)))) nil) #0 (/seq) None))",
                "sym_arity": 3,
                "dfa_symvars": ["Name", "Name", "Name"],
                "dfa_metavars": ["seqS"],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 1,
                "dfa_root": "seqS",
            },
            {
                "body": "(/seq (If (Compare (BinOp (BinOp (Name %3 Load) Sub (Name %2 Load)) Mod (Name %1 Load)) (list Eq) (list (Constant i0 None))) (/seq (Assign (list (Name %4 Store)) (BinOp (BinOp (BinOp (Name %3 Load) Sub (Name %2 Load)) FloorDiv (Name %1 Load)) Add (Constant i1 None)) None) (If #0 (/seq (Return (Name %4 Load))) (/seq))) (/seq)))",
                "sym_arity": 4,
                "dfa_symvars": ["Name", "Name", "Name", "Name"],
                "dfa_metavars": ["E"],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 1,
                "dfa_root": "seqS",
            },
            {
                "body": "(/subseq (FunctionDef %3 (arguments nil (list (arg %2 None None) (arg %1 None None)) None nil nil None nil) (/seq ?0 (Return (UnaryOp USub (Constant i1 None)))) nil None None) (Assign (list (Tuple (list (_starred_content (Name %5 Store)) (_starred_content (Name %4 Store))) Store)) (Call (Name g_map Load) (list (_starred_content (Name g_int Load)) (_starred_content (Call (Attribute (Call (Name g_input Load) nil nil) s_split Load) nil nil))) nil) None) (Expr (Call (Name g_print Load) (list (_starred_content (Call (Name %3 Load) (list (_starred_content (Name %5 Load)) (_starred_content (Name %4 Load))) nil))) nil)))",
                "sym_arity": 5,
                "dfa_symvars": ["Name", "Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": ["seqS"],
                "choice_arity": 1,
                "arity": 0,
                "dfa_root": "seqS",
            },
            {
                "body": "(FunctionDef %3 (arguments nil (list (arg %1 None None) (arg %2 None None)) None nil nil None nil) (/seq (If (Compare (Name %2 Load) (list Lt) (list (Name %1 Load))) (/seq (Return (Name %2 Load))) (/seq (Return (BinOp (Call (Name %3 Load) (list (_starred_content (Name %1 Load)) (_starred_content (BinOp (Name %2 Load) FloorDiv (Name %1 Load)))) nil) Add (BinOp (Name %2 Load) Mod (Name %1 Load))))))) nil None None)",
                "sym_arity": 3,
                "dfa_symvars": ["Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "S",
            },
            {
                "body": "(/subseq (While (Name %2 Load) (/seq (AugAssign (Name %3 Store) Add (BinOp (Name %2 Load) Mod (Name %1 Load))) (AugAssign (Name %2 Store) FloorDiv (Name %1 Load)) ?0) (/seq)) (If (Compare (Name %3 Load) (list Eq) (list (Name %4 Load))) (/seq (Return (Name %1 Load))) (/seq)))",
                "sym_arity": 4,
                "dfa_symvars": ["Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": ["seqS"],
                "choice_arity": 1,
                "arity": 0,
                "dfa_root": "seqS",
            },
            {
                "body": "(BinOp (Call (Name g_int Load) (list (_starred_content (BinOp (Name %1 Load) Pow (Constant f0.5 None)))) nil) Add (Constant i1 None))",
                "sym_arity": 1,
                "dfa_symvars": ["Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "E",
            },
            {
                "body": "(/seq (FunctionDef %3 (arguments nil (list (arg %2 None None) (arg %1 None None)) None nil nil None nil) (/seq ?0 (Return (UnaryOp USub (Constant i1 None)))) nil None None) (Assign (list (Tuple (list (_starred_content (Name %5 Store)) (_starred_content (Name %4 Store))) Store)) (Tuple (list (_starred_content (Call (Name g_int Load) (list (_starred_content (Call (Name g_input Load) nil nil))) nil)) (_starred_content (Call (Name g_int Load) (list (_starred_content (Call (Name g_input Load) nil nil))) nil))) Load) None) (Expr (Call (Name g_print Load) (list (_starred_content (Call (Name %3 Load) (list (_starred_content (Name %5 Load)) (_starred_content (Name %4 Load))) nil))) nil)))",
                "sym_arity": 5,
                "dfa_symvars": ["Name", "Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": ["seqS"],
                "choice_arity": 1,
                "arity": 0,
                "dfa_root": "seqS",
            },
            {
                "body": "(/subseq (/splice (fn_1 (/seq (If (Compare (Call (Name %4 Load) (list (_starred_content (Name %1 Load)) (_starred_content (Name %3 Load))) nil) (list Eq) (list (Name %2 Load))) (/seq (Return (Name %1 Load))) (/seq))) %3 %2 %1)) (For (Name %5 Store) #0 (/seq (Assign (list (Name %1 Store)) (BinOp (BinOp (BinOp (Name %3 Load) Sub (Name %2 Load)) FloorDiv (Name %5 Load)) Add (Constant i1 None)) None) (If (BoolOp And (list (Compare (Name %1 Load) (list Gt) (list (Constant i1 None))) (Compare (Call (Name %4 Load) (list (_starred_content (Name %1 Load)) (_starred_content (Name %3 Load))) nil) (list Eq) (list (Name %2 Load))))) (/seq (Return (Name %1 Load))) (/seq))) (/seq) None) (Return (UnaryOp USub (Constant i1 None))))",
                "sym_arity": 5,
                "dfa_symvars": ["Name", "Name", "Name", "Name", "Name"],
                "dfa_metavars": ["E"],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 1,
                "dfa_root": "seqS",
            },
            {
                "body": "(/subseq (FunctionDef %4 (arguments nil (list (arg %3 None None) (arg %2 None None)) None nil nil None nil) (/seq ?0 (Assign (list (Name %1 Store)) (Constant i0 None) None) (While (Name %3 Load) (/seq (AugAssign (Name %1 Store) Add (BinOp (Name %3 Load) Mod (Name %2 Load))) (AugAssign (Name %3 Store) FloorDiv (Name %2 Load))) (/seq)) (Return (Name %1 Load))) nil None None) (Assign (list (Tuple (list (_starred_content (Name %6 Store)) (_starred_content (Name %5 Store))) Store)) (Call (Name g_map Load) (list (_starred_content (Name g_int Load)) (_starred_content (Call (Attribute (Call (Name g_input Load) nil nil) s_split Load) nil nil))) nil) None) (Expr (Call (Name g_print Load) (list (_starred_content (Call (Name %7 Load) (list (_starred_content (Name %6 Load)) (_starred_content (Name %5 Load))) nil))) nil)))",
                "sym_arity": 7,
                "dfa_symvars": ["Name", "Name", "Name", "Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": ["seqS"],
                "choice_arity": 1,
                "arity": 0,
                "dfa_root": "seqS",
            },
            {
                "body": "(Call (Name g_range Load) (list (_starred_content (Call (Name g_int Load) (list (_starred_content (BinOp (Name %1 Load) Pow (Constant f0.5 None)))) nil)) (_starred_content (Constant i0 None)) (_starred_content (UnaryOp USub (Constant i1 None)))) nil)",
                "sym_arity": 1,
                "dfa_symvars": ["Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "E",
            },
            {
                "body": "(Subscript (Call (Name g_range Load) (list (_starred_content (Constant i1 None)) (_starred_content (fn_6 %1))) nil) (_slice_slice (Slice None None (UnaryOp USub (Constant i1 None)))) Load)",
                "sym_arity": 1,
                "dfa_symvars": ["Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "E",
            },
            {
                "body": "(BinOp (BinOp (BinOp (Name %3 Load) Sub (Name %2 Load)) FloorDiv (Name %1 Load)) Add (Constant i1 None))",
                "sym_arity": 3,
                "dfa_symvars": ["Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "E",
            },
            {
                "body": "(/subseq (Assign (list (Name %1 Store)) (Call (Name g_int Load) (list (_starred_content (Call #0 nil nil))) nil) None) (Assign (list (Name %2 Store)) (Call (Name g_int Load) (list (_starred_content (Call #0 nil nil))) nil) None) (Expr (Call (Name g_print Load) (list (_starred_content (Call (Name %3 Load) (list (_starred_content (Name %1 Load)) (_starred_content (Name %2 Load))) nil))) nil)))",
                "sym_arity": 3,
                "dfa_symvars": ["Name", "Name", "Name"],
                "dfa_metavars": ["E"],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 1,
                "dfa_root": "seqS",
            },
            {
                "body": "(/seq (Assign (list (Name %2 Store)) (Name %1 Load) None) (Assign (list (Name %3 Store)) (Constant i0 None) None) (While (Compare (Name %2 Load) (list Gt) (list (Constant i0 None))) (/seq (AugAssign (Name %3 Store) Add (BinOp (Name %2 Load) Mod (Name %4 Load))) (AugAssign (Name %2 Store) FloorDiv (Name %4 Load)) (If (Compare (Name %3 Load) (list Gt) (list (Name %5 Load))) (/seq Break) (/seq))) (/seq)) (If (Compare (Name %3 Load) (list Eq) (list (Name %5 Load))) (/seq (Return (Name %4 Load))) (/seq)))",
                "sym_arity": 5,
                "dfa_symvars": ["Name", "Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "seqS",
            },
            {
                "body": "(fn_1 (/seq (Assign (list (Name %4 Store)) (Name %3 Load) None) (Assign (list (Name %5 Store)) (Constant i0 None) None) (/splice (fn_5 %1 %4 %5 %2 (/choiceseq)))) %3 %2 %1)",
                "sym_arity": 5,
                "dfa_symvars": ["Name", "Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "seqS",
            },
            {
                "body": "(Return (UnaryOp USub (Constant i1 None)))",
                "sym_arity": 0,
                "dfa_symvars": [],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "S",
            },
            {
                "body": "(For (Name %4 Store) (Call (Name g_range Load) (list (_starred_content (fn_6 %2)) (_starred_content (Constant i0 None)) (_starred_content (UnaryOp USub (Constant i1 None)))) nil) (fn_2 (Compare (Name %1 Load) (list GtE) (list (Constant i2 None))) %4 %3 %2 %1) (/seq) None)",
                "sym_arity": 4,
                "dfa_symvars": ["Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "S",
            },
            {
                "body": "(If (Compare (Name %2 Load) (list Eq) (list (Name %1 Load))) (/seq (Return (BinOp (Name %1 Load) Add (Constant i1 None)))) (/seq))",
                "sym_arity": 2,
                "dfa_symvars": ["Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "S",
            },
            {
                "body": "(Compare (BinOp (BinOp (Name %3 Load) Sub (Name %2 Load)) Mod (Name %1 Load)) (list Eq) (list (Constant i0 None)))",
                "sym_arity": 3,
                "dfa_symvars": ["Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "E",
            },
            {
                "body": "(For (Name %1 Store) (Call (Name g_range Load) (list (_starred_content (Constant i2 None)) (_starred_content (fn_6 %3))) nil) (/seq (If (Compare (Call (Name %4 Load) (list (_starred_content (Name %1 Load)) (_starred_content (Name %3 Load))) nil) (list Eq) (list (Name %2 Load))) (/seq (Return (Name %1 Load))) (/seq))) (/seq) None)",
                "sym_arity": 4,
                "dfa_symvars": ["Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "S",
            },
            {
                "body": "(BinOp (Call (Name g_int Load) (list (_starred_content (BinOp (BinOp (Name %2 Load) Sub (Name %1 Load)) Pow (Constant f0.5 None)))) nil) Add (Constant i1 None))",
                "sym_arity": 2,
                "dfa_symvars": ["Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "E",
            },
            {
                "body": "(Call (Name g_map Load) (list (_starred_content (Name g_int Load)) (_starred_content (Call (Attribute (Call (Name g_input Load) nil nil) s_split Load) nil nil))) nil)",
                "sym_arity": 0,
                "dfa_symvars": [],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "E",
            },
            {
                "body": "(Tuple (list (_starred_content (Call (Name g_int Load) (list (_starred_content (Call (Name g_input Load) nil nil))) nil)) (_starred_content (Call (Name g_int Load) (list (_starred_content (Call (Name g_input Load) nil nil))) nil))) Load)",
                "sym_arity": 0,
                "dfa_symvars": [],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "E",
            },
            {
                "body": "(/splice (fn_1 (/seq (Assign (list (Name %4 Store)) (Name %3 Load) None) (Assign (list (Name %5 Store)) (Constant i0 None) None) (/splice (fn_5 %1 %4 %5 %2 (/choiceseq (If (Compare (Name %5 Load) (list Gt) (list (Name %2 Load))) (/seq Break) (/seq)))))) %3 %2 %1))",
                "sym_arity": 5,
                "dfa_symvars": ["Name", "Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "S",
            },
        ]

        test_abstr_configs = {}
        for i, entry in enumerate(stitch_abstrs):
            config = copy.deepcopy(entry)
            config["name"] = f"fn_{i+1}"
            config["body"] = ParsedAST.parse_s_expression(config["body"])
            test_abstr_configs[f"fn_{i+1}"] = config
        test_abstrs = [Abstraction(**x) for x in test_abstr_configs.values()]

        test_program = "(Module (/seq (/splice (fn_3 &s:1 &n:1 &find_base:0 &s:0 &n:0 (/choiceseq (fn_24 &b:1 &s:1 &n:1 &m:1 &sum_digits:1) (For (Name &q:1 Store) (Call (Name g_range Load) (list (_starred_content (Constant i1 None)) (_starred_content (fn_6 &n:1))) nil) (/seq (Assign (list (Name &b:1 Store)) (fn_12 &q:1 &s:1 &n:1) None) (If (Compare (BinOp (BinOp (Name &b:1 Load) Mult (Name &q:1 Load)) Add (Name &s:1 Load)) (list Eq) (list (Name &n:1 Load))) (/seq (Return (Name &b:1 Load))) (/seq))) (/seq) None))))) nil)"
        test_ast = ParsedAST.parse_s_expression(test_program)

        dfa = export_dfa(abstrs=test_abstrs)
        subset = DSLSubset.from_program(
            dfa,
            test_ast,
            test_ast.abstraction_calls_to_bodies_recursively(
                {x.name: x for x in test_abstrs}
            ),
            root="M",
        )
        print(subset)
        dsl = create_dsl(dfa, subset, "M")
        fam = ns.BigramProgramDistributionFamily(
            dsl,
            additional_preorder_masks=[
                lambda dist, dsl: DefUseChainPreorderMask(
                    dist, dsl, dfa=dfa, abstrs=test_abstrs
                )
            ],
            include_type_preorder_mask=False,
            node_ordering=lambda dist: PythonNodeOrdering(dist, test_abstrs),
        )

        annotated = test_ast.to_type_annotated_ns_s_exp(dfa, "M")
        fam.count_programs([[annotated]])

    def test_nested_generator_from_annie_simple(self):
        stitch_abstrs = [
            {
                "body": "(/subseq (If (Compare (Name %1 Load) (list Eq) (list (Name %2 Load))) (/seq (Return (BinOp (Name %1 Load) Add (Constant i1 None)))) (/seq)) (For (Name %3 Store) (Call (Name g_range Load) (list (_starred_content (Constant i2 None)) (_starred_content (BinOp (Call (Name g_int Load) (list (_starred_content (BinOp (Name %1 Load) Pow (Constant f0.5 None)))) nil) Add (Constant i1 None)))) nil) #0 (/seq) None))",
                "sym_arity": 3,
                "dfa_symvars": ["Name", "Name", "Name"],
                "dfa_metavars": ["seqS"],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 1,
                "dfa_root": "seqS",
            },
            {
                "body": "(/subseq (FunctionDef %3 (arguments nil (list (arg %2 None None) (arg %1 None None)) None nil nil None nil) (/seq ?0 (Return (UnaryOp USub (Constant i1 None)))) nil None None) (Assign (list (Tuple (list (_starred_content (Name %5 Store)) (_starred_content (Name %4 Store))) Store)) (Call (Name g_map Load) (list (_starred_content (Name g_int Load)) (_starred_content (Call (Attribute (Call (Name g_input Load) nil nil) s_split Load) nil nil))) nil) None) (Expr (Call (Name g_print Load) (list (_starred_content (Call (Name %3 Load) (list (_starred_content (Name %5 Load)) (_starred_content (Name %4 Load))) nil))) nil)))",
                "sym_arity": 5,
                "dfa_symvars": ["Name", "Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": ["seqS"],
                "choice_arity": 1,
                "arity": 0,
                "dfa_root": "seqS",
            },
            {
                "body": "(/subseq (While (Name %2 Load) (/seq (AugAssign (Name %3 Store) Add (BinOp (Name %2 Load) Mod (Name %1 Load))) (AugAssign (Name %2 Store) FloorDiv (Name %1 Load)) ?0) (/seq)) (If (Compare (Name %3 Load) (list Eq) (list (Name %4 Load))) (/seq (Return (Name %1 Load))) (/seq)))",
                "sym_arity": 4,
                "dfa_symvars": ["Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": ["seqS"],
                "choice_arity": 1,
                "arity": 0,
                "dfa_root": "seqS",
            },
            {
                "body": "(/splice (fn_1 (/seq (Assign (list (Name %4 Store)) (Name %3 Load) None) (Assign (list (Name %5 Store)) (Constant i0 None) None) (/splice (fn_3 %1 %4 %5 %2 (/choiceseq (If (Compare (Name %5 Load) (list Gt) (list (Name %2 Load))) (/seq Break) (/seq)))))) %3 %2 %1))",
                "sym_arity": 5,
                "dfa_symvars": ["Name", "Name", "Name", "Name", "Name"],
                "dfa_metavars": [],
                "dfa_choicevars": [],
                "choice_arity": 0,
                "arity": 0,
                "dfa_root": "S",
            },
        ]

        test_abstr_configs = {}
        for i, entry in enumerate(stitch_abstrs):
            config = copy.deepcopy(entry)
            config["name"] = f"fn_{i+1}"
            config["body"] = ParsedAST.parse_s_expression(config["body"])
            test_abstr_configs[f"fn_{i+1}"] = config
        test_abstrs = [Abstraction(**x) for x in test_abstr_configs.values()]
        # 1 3 5 24

        test_program = """
(Module
    (fn_2 &s:1 &n:1 &find_base:0 &s:0 &n:0
        (/choiceseq
            (fn_4 &b:1 &s:1 &n:1 &m:1 &sum_digits:1)
            ))
nil)
"""
        test_ast = ParsedAST.parse_s_expression(test_program)

        dfa = export_dfa(abstrs=test_abstrs)
        subset = DSLSubset.from_program(
            dfa,
            test_ast,
            test_ast.abstraction_calls_to_bodies_recursively(
                {x.name: x for x in test_abstrs}
            ),
            root="M",
        )
        print(subset)
        dsl = create_dsl(dfa, subset, "M")
        fam = ns.BigramProgramDistributionFamily(
            dsl,
            additional_preorder_masks=[
                lambda dist, dsl: DefUseChainPreorderMask(
                    dist, dsl, dfa=dfa, abstrs=test_abstrs
                )
            ],
            include_type_preorder_mask=False,
            node_ordering=lambda dist: PythonNodeOrdering(dist, test_abstrs),
        )

        annotated = test_ast.to_type_annotated_ns_s_exp(dfa, "M")
        fam.count_programs([[annotated]])

    @expand_with_slow_tests(len(load_stitch_output_set()), 10)
    def test_realistic_with_abstractions(self, i):
        x = copy.deepcopy(load_stitch_output_set()[i])
        abstractions = []
        for it, abstr in enumerate(x["abstractions"]):
            abstr["body"] = ParsedAST.parse_s_expression(abstr["body"])
            abstractions.append(Abstraction(name=f"fn_{it + 1}", **abstr))
        for code, rewritten in zip(x["code"], x["rewritten"]):
            print("*" * 80)
            for abstr in x["abstractions"]:
                print(abstr["body"].to_s_exp())
            print("*" * 80)
            print(
                ParsedAST.parse_s_expression(code)
                .abstraction_calls_to_stubs({x.name: x for x in abstractions})
                .to_python()
            )
            print("*" * 80)
            print(
                ParsedAST.parse_s_expression(rewritten)
                .abstraction_calls_to_stubs({x.name: x for x in abstractions})
                .to_python()
            )
            print("*" * 80)
            try:
                self.annotate_program(
                    code,
                    parser=ParsedAST.parse_s_expression,
                    abstrs=abstractions,
                )
            except AssertionError:
                continue
            self.annotate_program(
                rewritten,
                parser=ParsedAST.parse_s_expression,
                abstrs=abstractions,
            )
