import ast
import copy
import sys
import unittest

import neurosym as ns

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.data.stitch_output_set import (
    load_stitch_output_set,
    load_stitch_output_set_no_dfa,
)
from imperative_stitch.parser.parsed_ast import NodeAST, ParsedAST
from imperative_stitch.utils.def_use_mask.names import match_either
from tests.dsl_tests.dsl_test import fit_to
from tests.utils import (
    cwq,
    expand_with_slow_tests,
    load_annies_compressed_individual_programs,
    small_set_runnable_code_examples,
)


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
        dfa, _, fam, _ = fit_to(
            [program], parser=parser, abstrs=abstrs, include_type_preorder_mask=False
        )
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

    def assertAbstractionAnnotation(self, code, rewritten, abstractions):
        print("*" * 80)
        for abstr in abstractions:
            print(abstr.body.to_s_exp())
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
            return
        self.annotate_program(
            rewritten,
            parser=ParsedAST.parse_s_expression,
            abstrs=abstractions,
        )


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

    def test_exception_named(self):
        code = self.annotate_program(
            cwq(
                """
                try:
                    x = 2
                except Exception as e:
                    x = e
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                try:
                    x?Exception$e = 2
                except Exception?x as e?Exception$x:
                    x?Exception$e = e?Exception$x
                """
            ).strip(),
        )

    def test_exception_unnamed(self):
        code = self.annotate_program(
            cwq(
                """
                try:
                    x = 2
                except Exception:
                    x = x
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                try:
                    x?Exception = 2
                except Exception?x:
                    x?Exception = x?Exception
                """
            ).strip(),
        )

    def test_complicated_type_annot(self):
        code = self.annotate_program(
            cwq(
                """
                x: List[Dict[str, int]] = []
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                x: List[Dict[str, int]] = []
                """
            ).strip(),
        )

    @expand_with_slow_tests(200, -1)
    def test_realistic(self, i):
        if i in {22, 31, 41, 57, 95, 100, 106, 109, 112, 114, 119, 181, 182}:
            # forward declaration of
            # input for 22/41/100/119
            # n for 31/57/112/114
            # m for 95
            # sp for 106
            # mp for 109
            # dp for 181
            # lo for 182 [this one's weird]
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
        return Abstraction.of(name, ParsedAST.parse_python_statements(content), "seqS")

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
                Abstraction.of(
                    "fn_1",
                    "(Assign (list (Name %1 Store)) (Name %2 Load) None)",
                    "S",
                    dfa_symvars=["Name"] * 2,
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
                Abstraction.of(
                    "fn_1",
                    "(Assign (list (Name %2 Store)) (Name %1 Load) None)",
                    "S",
                    dfa_symvars=["Name"] * 2,
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
                Abstraction.of(
                    "fn_1",
                    "(Assign (list (Name %1 Store)) #0 None)",
                    "S",
                    dfa_symvars=["Name"],
                    dfa_metavars=["E"],
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
                Abstraction.of(
                    "fn_1",
                    "(/seq (Assign (list (Name %2 Store)) (Name %1 Load) None) (Assign (list (Name %2 Store)) (Name %1 Load) None))",
                    "seqS",
                    dfa_symvars=["Name"] * 2,
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
                Abstraction.of(
                    "fn_1",
                    "(/seq (Assign (list (Name %2 Store)) (Name %1 Load) None) (Assign (list (Name %2 Store)) #0 None))",
                    "seqS",
                    dfa_symvars=["Name"] * 2,
                    dfa_metavars=["E"],
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
                Abstraction.of(
                    "fn_1",
                    "(/seq #0 (Assign (list (Name %2 Store)) (Name %1 Load) None))",
                    "seqS",
                    dfa_symvars=["Name"] * 2,
                    dfa_metavars=["S"],
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

    def test_definition_in_choiceseq(self):
        code = cwq(
            """
            b = 2
            "~(/splice (fn_1 &c:0 &a:0 (/choiceseq (Assign (list (Name &c:0 Store)) (Name &b:0 Load) None))))"
            a = a
            """
        )
        annotated = self.annotate_program(
            code,
            parser=self.parse_with_hijacking,
            abstrs=[
                Abstraction.of(
                    "fn_1",
                    "(/seq ?0 (Assign (list (Name %2 Store)) (Name %1 Load) None))",
                    "seqS",
                    dfa_symvars=["Name"] * 2,
                    dfa_choicevars=["seqS"],
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
                fn_1(__ref__(c?b), __ref__(a?b$c), __code__('c?a$b = b'))
                a?b$c = a?b$c
                """
            ).strip(),
        )

    def test_impossible_likelihood_bug(self):
        # ensure that the likelihood computation doesn't crash
        # see https://github.com/kavigupta/neurosym-lib/pull/78 which fixed this
        code = cwq(
            """
            "~(/splice (fn_1 &b:0 &a:0 (/choiceseq)))"
            a = a
            """
        )
        program = self.parse_with_hijacking(code)
        abstrs = [
            Abstraction.of(
                "fn_1",
                "(/seq (Assign (list (Name %2 Store)) (Name %1 Load) None) ?0)",
                "seqS",
                dfa_symvars=["Name"] * 2,
                dfa_choicevars=["seqS"],
            )
        ]
        dfa, _, fam, dist = fit_to([program], parser=lambda x: x, abstrs=abstrs)
        print(program)
        print(dist)
        self.assertEqual(
            fam.compute_likelihood(dist, program.to_type_annotated_ns_s_exp(dfa, "M")),
            -float("inf"),
        )

    def test_out_of_order_within_abstraction(self):
        fn_3 = Abstraction.of(
            "fn_3",
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
            """,
            "S",
            dfa_symvars=["Name"],
            dfa_metavars=["E", "E"],
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
                Abstraction.of("fn_1", "(Name &b:0 Load)", "E"),
                Abstraction.of(
                    "fn_2",
                    "(Assign (list (Name %1 Store)) #0 None)",
                    "S",
                    dfa_symvars=["Name"],
                    dfa_metavars=["E"],
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


class DefUseMaskWithAbstractionsRealisticTest(DefUseMaskTestGeneric):
    def check_use_mask(self, x):
        x = copy.deepcopy(x)
        abstractions = [
            Abstraction.of(name=f"fn_{it + 1}", **abstr)
            for it, abstr in enumerate(x["abstractions"])
        ]
        for code, rewritten in zip(x["code"], x["rewritten"]):
            self.assertAbstractionAnnotation(code, rewritten, abstractions)

    @expand_with_slow_tests(len(load_stitch_output_set()), 10)
    def test_realistic_with_abstractions(self, i):
        self.check_use_mask(load_stitch_output_set()[i])

    @expand_with_slow_tests(len(load_stitch_output_set_no_dfa()), 10)
    def test_realistic_with_abstractions_no_dfa(self, i):
        self.check_use_mask(load_stitch_output_set_no_dfa()[i])


class DefUseMaskWithAbstractionsRealisticAnnieSetTest(DefUseMaskTestGeneric):
    @expand_with_slow_tests(len(load_annies_compressed_individual_programs()), 10)
    def test_annies_compressed_with_abstractions(self, i):
        abstrs, rewritten = load_annies_compressed_individual_programs()[i]
        abstrs_dict = {x.name: x for x in abstrs}

        code = (
            ParsedAST.parse_s_expression(rewritten)
            .abstraction_calls_to_bodies_recursively(abstrs_dict)
            .to_s_exp()
        )
        self.assertAbstractionAnnotation(code, rewritten, abstrs)


class DefUseMaskWihAbstractionsLikliehoodAnnieSetTest(DefUseMaskTestGeneric):
    @expand_with_slow_tests(len(load_annies_compressed_individual_programs()), 10)
    def test_annies_compressed_realistic(self, i):
        abstrs, rewritten = load_annies_compressed_individual_programs()[i]
        rewritten = ParsedAST.parse_s_expression(rewritten)
        code = rewritten.abstraction_calls_to_bodies({x.name: x for x in abstrs})
        dfa, _, fam, dist = fit_to([rewritten, code], parser=lambda x: x, abstrs=abstrs)
        # should not error
        fam.compute_likelihood(dist, rewritten.to_type_annotated_ns_s_exp(dfa, "M"))
