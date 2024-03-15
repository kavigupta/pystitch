import unittest
from textwrap import dedent

import neurosym as ns

from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.preorder_mask import NAME_REGEX, DefUseChainPreorderMask
from tests.dsl_tests.dsl_test import fit_to


class EnumerateFittedDslTest(unittest.TestCase):
    def annotate_alternates(self, chosen, alts):
        print(chosen, alts)
        mat = NAME_REGEX.match(chosen)
        if not mat:
            return chosen
        name, scope = mat.groups()
        alts = [NAME_REGEX.match(alt) for alt in alts]
        alts = {x.group(1) for x in alts if x} - {name}
        alts = sorted(alts)
        if alts:
            name = f"{name}?{','.join(alts)}"
        return f"const-&{name}:{scope}~Name"

    def annotate_program(self, program):
        dfa, dsl, fam, _ = fit_to([program])
        return ParsedAST.parse_s_expression(
            ns.render_s_expression(
                ns.annotate_with_alternate_symbols(
                    ParsedAST.parse_python_module(program).to_type_annotated_ns_s_exp(
                        dfa, "M"
                    ),
                    fam.tree_distribution_skeleton,
                    lambda tree_dist: DefUseChainPreorderMask(tree_dist, dsl),
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
