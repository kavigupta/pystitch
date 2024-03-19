import sys
import unittest
from textwrap import dedent

import neurosym as ns

from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.def_use_mask import NAME_REGEX
from tests.dsl_tests.dsl_test import fit_to


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
            name = f"{name}?{','.join(alts)}"
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
            dedent(
                """
                x?y,z = 2
                y?x,z = x
                z?x,y = y?x
                """
            ).strip(),
        )

    def test_subscript_on_lhs(self):
        code = self.annotate_program("x = [2, 3, 4]; x[2] = x[0]; y = 2")
        print(code)
        self.assertEqual(
            code.strip(),
            dedent(
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
            dedent(
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
        [x?y,z, y?x,z] = (2, 3)
        x?y,z, y?x,z = (x?y, y?x)
        z?x,y = x?y
        """
        up_to_310 = """
        [x?y,z, y?x,z] = (2, 3)
        (x?y,z, y?x,z) = (x?y, y?x)
        z?x,y = x?y
        """
        self.assertEqual(
            code.strip(),
            dedent(up_to_310 if sys.version_info < (3, 11) else past_310).strip(),
        )

    def test_basic_import(self):
        # the 2 in front is necessary to force the import to not be pulled
        code = self.annotate_program("2; import os; import sys as y; x = os; x = os")
        print(code)
        self.assertEqual(
            code.strip(),
            dedent(
                """
                2
                import os?x,y
                import sys as y?os,x
                x?os,y = os?y
                x?os,y = os?x,y
                """
            ).strip(),
        )

    def test_function_call(self):
        code = self.annotate_program(
            dedent(
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
            dedent(
                """
                def f?x,y,z(x?f,y,z):
                    z?f,x,y = x?f
                    return x?f,z
                y?f,x,z = f(2)
                """
            ).strip(),
        )

    # @expand_with_slow_tests(1000)
    # def test_semantics(self, i):
    #     example = small_set_runnable_code_examples()[i]["solution"]
    #     print(example)
    #     code = self.annotate_program(example)
    #     print(code)
