import unittest
from fractions import Fraction

import neurosym as ns
import numpy as np

from imperative_stitch.parser import converter
from tests.dsl_tests.utils import fit_to


class TestLikelihoodFittedDSL(unittest.TestCase):
    def compute_likelihood(self, corpus, program):
        dfa, _, fam, dist = fit_to(corpus, smoothing=False)
        program = ns.to_type_annotated_ns_s_exp(
            ns.python_to_python_ast(program), dfa, "M"
        )
        like = fam.compute_likelihood(dist, program)
        like = Fraction.from_float(float(np.exp(like))).limit_denominator()
        results = fam.compute_likelihood_per_node(dist, program)
        results = [
            (
                ns.render_s_expression(x),
                Fraction.from_float(float(np.exp(y))).limit_denominator(),
            )
            for x, y in results
            if y != 0  # remove zero log-likelihoods
        ]
        print(like)
        print(results)
        return like, results

    def test_likelihood_with_abstractions(self):
        # test from annie
        test_programs = [
            "(fn_1 (fn_2) (fn_2))",
            "(fn_1 (fn_3 (fn_3 (fn_2))) (fn_3 (fn_2)))",
        ]
        test_programs_ast = [converter.s_exp_to_python_ast(p) for p in test_programs]
        test_dfa = {"E": {"fn_1": ["E", "E"], "fn_2": [], "fn_3": ["E"]}}

        test_subset = ns.PythonDSLSubset.from_programs(
            test_dfa,
            *test_programs_ast,
            root="E",
        )
        test_dsl = ns.create_python_dsl(test_dfa, test_subset, "E")

        test_fam = ns.BigramProgramDistributionFamily(test_dsl)
        test_counts = test_fam.count_programs(
            [[ns.to_type_annotated_ns_s_exp(test_programs_ast[0], test_dfa, "E")]]
        )
        test_dist = test_fam.counts_to_distribution(test_counts)[0]
        likelihood = test_fam.compute_likelihood(
            test_dist,
            ns.to_type_annotated_ns_s_exp(test_programs_ast[1], test_dfa, "E"),
        )
        self.assertEqual(likelihood, -np.inf)
        result = test_fam.compute_likelihood_per_node(
            test_dist,
            ns.to_type_annotated_ns_s_exp(test_programs_ast[1], test_dfa, "E"),
        )
        result = [
            (
                ns.render_s_expression(x),
                Fraction.from_float(float(np.exp(y))).limit_denominator(),
            )
            for x, y in result
            if y != 0  # remove zero log-likelihoods
        ]
        print(result)
        self.assertEqual(
            result,
            [
                ("(fn_3~E (fn_3~E (fn_2~E)))", Fraction(0, 1)),
                ("(fn_3~E (fn_2~E))", Fraction(0, 1)),
                ("(fn_2~E)", Fraction(0, 1)),
                ("(fn_3~E (fn_2~E))", Fraction(0, 1)),
                ("(fn_2~E)", Fraction(0, 1)),
            ],
        )
