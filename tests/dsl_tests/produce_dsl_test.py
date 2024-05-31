import unittest

import neurosym as ns

from imperative_stitch.parser import converter

from ..utils import assertDSL


class ProduceDSLWithAbstractionsTest(unittest.TestCase):
    def test_fit_to_programs_including_abstractions(self):
        new_dfa = {"E": {}, "seqS": {}}
        new_dfa["E"]["fn_1"] = []
        new_dfa["E"]["fn_2"] = ["seqS"]
        new_dfa["seqS"]["fn_param_1"] = ["E"]
        test_programs = [
            converter.s_exp_to_python_ast(p)
            for p in ["(fn_1)", "(fn_2 (fn_param_1 (fn_1)))"]
        ]
        new_subset = ns.PythonDSLSubset.from_programs(new_dfa, *test_programs, root="E")
        new_dsl = ns.create_python_dsl(new_dfa, new_subset, "E")
        assertDSL(
            self,
            new_dsl.render(),
            """
            fn_1~E :: () -> E
            fn_2~E :: seqS -> E
            fn_param_1~seqS :: E -> seqS
            """,
        )
