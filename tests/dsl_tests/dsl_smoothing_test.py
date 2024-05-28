import unittest

import neurosym as ns
import numpy as np

from imperative_stitch.parser.python_ast import PythonAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.def_use_mask.mask import DefUseChainPreorderMask
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering
from imperative_stitch.utils.export_as_dsl import (
    DSLSubset,
    create_dsl,
    create_smoothing_mask,
)


class DSLSmoothingTest(unittest.TestCase):
    def setUp(self):
        self.dfa = None
        self.fam = None
        self.dist = None

    def dist_for_smoothing(
        self, programs, extra_programs=(), root="M", do_smooth_masking=False
    ):
        programs = [PythonAST.parse_python_module(program) for program in programs]
        extra_programs = [
            PythonAST.parse_python_module(program) for program in extra_programs
        ]
        dfa = export_dfa()
        dsl = create_dsl(
            dfa,
            DSLSubset.from_program(dfa, *programs, *extra_programs, root=root),
            root,
        )
        if do_smooth_masking:
            dsl_subset = create_dsl(
                dfa,
                DSLSubset.from_program(dfa, *programs, root=root),
                root,
            )
            smooth_mask = create_smoothing_mask(dsl, dsl_subset)
        else:
            smooth_mask = None
        fam = ns.BigramProgramDistributionFamily(
            dsl,
            additional_preorder_masks=[
                lambda dist, dsl: DefUseChainPreorderMask(dist, dsl, dfa, ())
            ],
            node_ordering=lambda dist: PythonNodeOrdering(dist, ()),
        )
        counts = fam.count_programs(
            [[program.to_type_annotated_ns_s_exp(dfa, root) for program in programs]]
        )
        dist = fam.counts_to_distribution(counts)[0]
        dist = dist.bound_minimum_likelihood(1e-6, smooth_mask)
        self.dfa = dfa
        self.fam = fam
        self.dist = dist

    def likelihood(self, program):
        program = PythonAST.parse_python_module(program)
        log_p = self.fam.compute_likelihood(
            self.dist, program.to_type_annotated_ns_s_exp(self.dfa, "M")
        )
        return log_p

    def assertLikeli(self, prog, reciprocal_prob):
        self.assertAlmostEqual(self.likelihood(prog), -np.log(reciprocal_prob), 3)

    def standard_checks(self):
        # 1/2 [2], 1/2 [5]
        self.assertLikeli("x = 2 + 5", 2 * 2)
        # 1/2 [2], 1/1e6 [+], 1/2 [5], 1/2 [5]
        self.assertLikeli("x = 2 + (2 + 5)", 2 * 10**6 * 2 * 2)

    def test_smoothing_no_extra(self):
        self.dist_for_smoothing(["x = 2 + 5"])
        self.standard_checks()

    def test_smoothing_with_extra(self):
        self.dist_for_smoothing(["x = 2 + 5"], ["x = 2 * 3"])
        self.standard_checks()
        # 1/1e6 [*], 1/2 [2], 1/2 [5]
        self.assertLikeli("x = 2 * 5", 10**6 * 2 * 2)

    def test_smoothing_with_extra_subset_mask(self):
        self.dist_for_smoothing(["x = 2 + 5"], ["x = 2 * 3"], do_smooth_masking=True)
        self.standard_checks()
        # 1/1e6 [*], 1/2 [2], 1/2 [5]
        self.assertLikeli("x = 2 * 5", np.inf)
