import ast
import copy
import sys
import unittest
from fractions import Fraction

import neurosym as ns
import numpy as np

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.data.stitch_output_set import (
    load_stitch_output_set,
    load_stitch_output_set_no_dfa,
)
from imperative_stitch.parser.parsed_ast import NodeAST, ParsedAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.def_use_mask.canonicalize_de_bruijn import (
    uncanonicalize_de_bruijn,
)
from imperative_stitch.utils.def_use_mask.mask import DefUseChainPreorderMask
from imperative_stitch.utils.def_use_mask.names import match_either
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl
from tests.dsl_tests.dsl_test import fit_to
from tests.utils import (
    cwq,
    expand_with_slow_tests,
    load_annies_compressed_individual_programs,
    small_set_runnable_code_examples,
)


class DefUseMaskTestGeneric(unittest.TestCase):
    def test_canonicalize_de_bruijn(self):
        programs = ["x = 2; y = x + 1; z = x + y; x = 3"]
        programs = [ParsedAST.parse_python_module(program) for program in programs]
        dfa = export_dfa()
        sexp = programs[0].to_type_annotated_de_bruijn_ns_s_exp(
            dfa, "M", de_bruijn_limit=2
        )
        self.maxDiff = None
        expected = """
        (Module~M 
            (/seq~seqS~4
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-0~Name) (Store~Ctx)))
                    (Constant~E (const-i2~Const) (const-None~ConstKind))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-0~Name) (Store~Ctx)))
                    (BinOp~E (Name~E (dbvar-1~Name) (Load~Ctx)) (Add~O) (Constant~E (const-i1~Const) (const-None~ConstKind)))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-0~Name) (Store~Ctx)))
                    (BinOp~E (Name~E (dbvar-2~Name) (Load~Ctx)) (Add~O) (Name~E (dbvar-1~Name) (Load~Ctx)))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-successor~Name (dbvar-2~Name)) (Store~Ctx)))
                    (Constant~E (const-i3~Const) (const-None~ConstKind))
                    (const-None~TC)))
            (list~_TI_~0))
        """
        self.assertEqual(
            ns.render_s_expression(sexp),
            ns.render_s_expression(ns.parse_s_expression(expected)),
        )

        self.assertEqual(
            ParsedAST.from_type_annotated_de_bruijn_ns_s_exp(
                ns.render_s_expression(sexp), dfa
            ).to_python(),
            cwq(
                """
                __0 = 2
                __1 = __0 + 1
                __2 = __0 + __1
                __0 = 3
                """
            ),
        )

    def test_likelihood(self):
        fit_to = ["x = 2; y = x; y = x"]
        # this program is $0 = 2; $0 = $1; $1 = $2
        test_program = "x = 2; y = x; z = y"
        # this program is $0 = 2; $0 = $1; $0 = $1
        # should have a likelihood of
        # (2/3)^3 [$0 on LHS]
        # (1/3)^2 [$1 on RHS]
        # (1/3)^1 [2 on LHS]

        dfa = export_dfa()

        fit_to_prog = [
            ParsedAST.parse_python_module(program).to_type_annotated_de_bruijn_ns_s_exp(
                dfa, "M", de_bruijn_limit=2
            )
            for program in fit_to
        ]
        test_program = ParsedAST.parse_python_module(
            test_program
        ).to_type_annotated_de_bruijn_ns_s_exp(dfa, "M", de_bruijn_limit=2)
        print(test_program)

        dsl = create_dsl(dfa, DSLSubset.from_type_annotated_s_exps(fit_to_prog), "M")
        fam = ns.BigramProgramDistributionFamily(
            dsl,
            additional_preorder_masks=[],  # note: no need if we are using de bruijn
            include_type_preorder_mask=True,
            node_ordering=lambda dist: PythonNodeOrdering(dist, ()),
        )
        counts = fam.count_programs([fit_to_prog])
        dist = fam.counts_to_distribution(counts)[0]

        self.assertEqual(
            Fraction.from_float(
                float(np.exp(fam.compute_likelihood(dist, test_program)))
            ).limit_denominator(1000),
            Fraction(2**3, 3**6),
        )
