import neurosym as ns
import numpy as np
from typing import Callable, List, Dict, Tuple

from ..parser import ParsedAST
from ..enumerate.production_factory import ProductionFactory, Config, initialize_factory
from imperative_stitch.utils.export_as_dsl import (
    DSLSubset,
    create_dsl,
    create_smoothing_mask,
)
from imperative_stitch.utils.classify_nodes import export_dfa

from imperative_stitch.utils.def_use_mask import DefUseChainPreorderMask
from imperative_stitch.utils.def_use_mask.ordering import PythonNodeOrdering

DE_BRUIJN_LIMIT = 2


class LikelihoodCalculator:
    def __init__(self, abstractions, corpus, target, canonicalize):
        self.factory = self.setup_factory(abstractions, corpus, target, canonicalize)
        self.dfa = self.make_dfa()
        self.original_programs = self.factory.expand_programs()
        self.abstrs = [v.ast for v in self.factory.abstractions.values()]

        programs = self.factory.expand_programs()
        roots = ["M"] * len(programs)  # assume all programs are rooted at "M"
        self.programs = programs
        self.roots = roots

    def setup_factory(
        self,
        abstractions: List[Dict],
        programs: List[str],
        target: str,
        fn_transform_vars: Callable[[str], str] = None,
    ) -> ProductionFactory:
        if fn_transform_vars is not None:
            programs = [fn_transform_vars(p) for p in programs]
            target = fn_transform_vars(target)
        return initialize_factory(abstractions, programs, target)

    def make_dfa(self):
        abstrs = {k: v.ast for k, v in self.factory.abstractions.items()}
        dfa = export_dfa(abstrs=abstrs)
        return self.factory.expand_dfa(dfa)

    def make_dsl_and_family(self, programs, roots, de_bruijn, use_defvar_mask):
        dsl = make_dsl(self.dfa, programs, roots, self.abstrs, de_bruijn=de_bruijn)
        fam = make_bigram_fam(
            dsl,
            use_defvar_mask,
            self.abstrs,
            self.dfa,
            de_bruijn=de_bruijn,
        )
        return dsl, fam

    def programs_to_count(self, programs, use_de_bruijn):
        if not use_de_bruijn:
            return [p.to_type_annotated_ns_s_exp(self.dfa, "M") for p in programs]
        return [
            p.to_type_annotated_de_bruijn_ns_s_exp(
                self.dfa,
                "M",
                de_bruijn_limit=DE_BRUIJN_LIMIT,
                abstrs=self.abstrs,
            )
            for p in programs
        ]

    def fit_family_to_distributions(
        self, fam, programs_to_count
    ) -> ns.BigramProgramCountsBatch:
        counts = fam.count_programs([programs_to_count])
        dist = fam.counts_to_distribution(counts)[0]
        return dist

    def make_target_program(factory, config, abstrs, dfa, use_de_bruijn):
        target_program = ParsedAST.parse_s_expression(factory.rewrite_solution(config))
        if use_de_bruijn:
            return target_program.to_type_annotated_de_bruijn_ns_s_exp(
                dfa, "M", abstrs=abstrs, de_bruijn_limit=DE_BRUIJN_LIMIT
            )
        return target_program.to_type_annotated_ns_s_exp(dfa, "M")

    def gather_programs(
        self,
        config: Config,
        corpus: List[ParsedAST],
        add_abstractions_to_dsl: bool = True,
        include_unexpanded: bool = True,
    ) -> Tuple[List[ParsedAST], List[str]]:
        programs, roots = self.programs[:], self.roots[:]
        for program in corpus:
            programs.append(program)
            roots.append("M")
        if include_unexpanded:
            for program in self.factory.rewrite_all(config, include_sols=False):
                programs.append(ParsedAST.parse_s_expression(program))
                roots.append("M")
        if add_abstractions_to_dsl:
            for abstraction in self.factory.abstractions.values():
                programs.append(abstraction.body)
                roots.append(abstraction.dfa_root)
        return programs, tuple(roots)

    def get_likelihood(self, fam, dist, target_program, per_node_likelihood):
        """
        Calculate the likelihood of generaing the target program using the
        given family. Return 1 if the target program contains symbols
        that are not present in the family. Otherwise, return a likelihood <= 0.
        """
        try:
            likelihood = fam.compute_likelihood(dist, target_program)
            if per_node_likelihood:
                likelihood = [
                    (ns.render_s_expression(node), prob) for node, prob in likelihood
                ]
        except Exception as e:
            print(e, flush=True)
            likelihood = 1
        return likelihood

    def make_target_program(self, config, use_de_bruijn):
        raw_solution = self.factory.rewrite_solution(config)
        target_program = ParsedAST.parse_s_expression(raw_solution)
        if use_de_bruijn:
            return target_program.to_type_annotated_de_bruijn_ns_s_exp(
                self.dfa, "M", abstrs=self.abstrs, de_bruijn_limit=DE_BRUIJN_LIMIT
            )
        return target_program.to_type_annotated_ns_s_exp(self.dfa, "M")

    def calculate_likelihood(
        self,
        config: Config = Config(),
        aug_corpus: List[ParsedAST] = [],
        smooth_dist: float = None,
        use_smooth_mask: bool = False,
        use_defvar_mask: bool = False,
        add_abstractions_to_dsl: bool = False,
        per_node_likelihood: bool = False,
        merge_dists: bool = False,
        de_bruijn: bool = False,
    ):
        programs, roots = self.gather_programs(
            config,
            aug_corpus,
            add_abstractions_to_dsl,
            include_unexpanded=not (use_defvar_mask or de_bruijn),
        )

        roots = roots if add_abstractions_to_dsl else "M"

        formatted_programs = self.factory.rewrite_all(config)
        corpus_to_fit = [ParsedAST.parse_s_expression(p) for p in formatted_programs]
        dsl, fam = self.make_dsl_and_family(programs, roots, de_bruijn, use_defvar_mask)
        programs_to_count = self.programs_to_count(corpus_to_fit, de_bruijn)
        dist = self.fit_family_to_distributions(fam, programs_to_count)

        if merge_dists:
            aug_corpus_to_fit = [
                p.to_type_annotated_ns_s_exp(self.dfa, "M") for p in aug_corpus
            ]
            aug_corpus_dist = self.fit_family_to_distributions(fam, aug_corpus_to_fit)
            aug_corpus_dist = aug_corpus_dist.bound_minimum_likelihood(0.01)
            dist = dist.mix_with_other(aug_corpus_dist, 0.01)
        elif smooth_dist is not None:
            dsl_subset = make_dsl(self.original_programs, "M")
            smooth_mask = (
                create_smoothing_mask(dsl, dsl_subset) if use_smooth_mask else None
            )
            dist = dist.bound_minimum_likelihood(smooth_dist, smooth_mask)

        target_program = self.make_target_program(config, de_bruijn)
        return self.get_likelihood(fam, dist, target_program, per_node_likelihood)


def make_dsl(dfa, programs, roots, abstrs=[], de_bruijn=False):
    if not de_bruijn:
        subset = DSLSubset.from_program(
            dfa,
            *programs,
            root=roots,
            abstrs=abstrs,
        )
    else:
        subset = DSLSubset.from_program(
            dfa,
            *programs,
            root=roots,
            abstrs=abstrs,
            to_s_exp=lambda p, dfa, root: p.to_type_annotated_de_bruijn_ns_s_exp(
                dfa,
                root,
                de_bruijn_limit=DE_BRUIJN_LIMIT,
                abstrs=abstrs,
            ),
        )
    return create_dsl(dfa, subset, "M")


def make_bigram_fam(
    dsl,
    use_defvar_mask,
    abstrs,
    dfa=None,
    de_bruijn=False,
):
    if not de_bruijn and not use_defvar_mask:
        return ns.BigramProgramDistributionFamily(dsl)

    return ns.BigramProgramDistributionFamily(
        dsl,
        additional_preorder_masks=[
            lambda dist, dsl: DefUseChainPreorderMask(dist, dsl, dfa=dfa, abstrs=abstrs)
        ],
        include_type_preorder_mask=True,
        node_ordering=lambda dist: PythonNodeOrdering(dist, abstrs),
    )


def calculate(target, abstractions, corpus, canonicalize, **kwargs):
    calculator = LikelihoodCalculator(abstractions, corpus, target, canonicalize)
    return calculator.calculate_likelihood(**kwargs)
