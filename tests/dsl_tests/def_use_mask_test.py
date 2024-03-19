import sys
import unittest

import neurosym as ns

from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.def_use_mask.names import NAME_REGEX
from tests.dsl_tests.dsl_test import fit_to
from tests.utils import cwq, expand_with_slow_tests, small_set_runnable_code_examples


class EnumerateFittedDslTest(unittest.TestCase):
    def annotate_alternates(self, chosen, alts):
        mat = NAME_REGEX.match(chosen)
        if not mat:
            return chosen
        name, scope, _ = mat.groups()
        alts = [NAME_REGEX.match(alt) for alt in alts]
        alts = {x.group(1) for x in alts if x}
        self.assertIn(name, alts)
        alts.remove(name)
        alts = sorted(alts)
        if alts:
            name = f"{name}?{'$'.join(alts)}"
        return f"const-&{name}:{scope}~Name"

    def annotate_program(self, program):
        dfa, _, fam, _ = fit_to([program])
        return ParsedAST.parse_s_expression(
            ns.render_s_expression(
                ns.annotate_with_alternate_symbols(
                    ParsedAST.parse_python_module(program).to_type_annotated_ns_s_exp(
                        dfa, "M"
                    ),
                    fam.tree_distribution_skeleton,
                    self.annotate_alternates,
                )
            )
        ).to_python()

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
                x = 2
                y.z = 3
                x = x
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

    def test_basic_import(self):
        # the 2 in front is necessary to force the import to not be pulled
        code = self.annotate_program("2; import os; import sys as y; x = os; x = os")
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                2
                import os?x$y
                import sys as y?os$x
                x?os$y = os?y
                x?os$y = os?x$y
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

    def test_single_comprehension(self):
        code = self.annotate_program(
            cwq(
                """
                a = 2
                [b for b in range(a) if b == a]
                print(a)
                """
            )
        )
        print(code)
        self.assertEqual(
            code.strip(),
            cwq(
                """
                a?b = 2
                [b?a for b?a in range(a) if b?a == a?b]
                print(a)
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
                a?b$c$d$e$f$g = 2
                [b?a for b?a$c$d$e$f$g in range(a)]
                (c?a for c?a$b$d$e$f$g in range(a))
                {c?a for c?a$b$d$e$f$g in range(a)}
                {d?a: a?d for d?a$b$c$e$f$g in range(a)}
                [e?a$f$g + f?a$e$g + g?a$e$f
                    for e?a$b$c$d$f$g in range(a)
                    for f?a$b$c$d$e$g in range(e?a)
                    for g?a$b$c$d$e$f in range(f?a$e)]
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
                    print(y)
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
                    print(y?x)
                z?x$y = x?y
                """
            ).strip(),
        )

    @expand_with_slow_tests(1000, -1)
    def test_realistic(self, i):
        example = small_set_runnable_code_examples()[i]["solution"]
        print(example)
        code = self.annotate_program(example)
        print(code)
