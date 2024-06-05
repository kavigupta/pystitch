import json
import os

from typing import List

from functools import partial
from imperative_stitch.enumerate.runner import (
    get_all_likelihoods,
    COMPRESSED_SAVE_FILE,
)
from imperative_stitch.enumerate.calculate_likelihood import GPT_3, GPT_4
from imperative_stitch.utils.analysis_utils import unify_scope
from imperative_stitch.parser import ParsedAST
from imperative_stitch.compress.julia_stitch import run_julia_stitch

JL_STITCH_DIR = ""

PYTHON_CORPUS = json.load(open("", "r"))
PYTHON_AST_CORPUS = [
    ParsedAST.parse_python_module("def f():\n" + p) for p in PYTHON_CORPUS
]

GPT_4_RESPONSES = ""
GPT_3_RESPONSES = ""

GPT_4_RESULTS = ""
GPT_3_RESULTS = ""


EXPERIMENTS = [
    dict(),
    dict(smooth_dist=1e-3),
    dict(smooth_dist=1e-3, use_smooth_mask=True),
    dict(aug_corpus=PYTHON_AST_CORPUS, smooth_dist=1e-3),
    dict(aug_corpus=PYTHON_AST_CORPUS, smooth_dist=1e-3, use_smooth_mask=True),
    dict(aug_corpus=PYTHON_AST_CORPUS, smooth_dist=1e-3, add_abstractions_to_dsl=True),
    dict(
        aug_corpus=PYTHON_AST_CORPUS,
        smooth_dist=1e-3,
        add_abstractions_to_dsl=True,
        use_smooth_mask=True,
    ),
    dict(aug_corpus=PYTHON_AST_CORPUS, add_abstractions_to_dsl=True),
    dict(
        aug_corpus=PYTHON_AST_CORPUS,
        add_abstractions_to_dsl=True,
        expand_params=False,
    ),
    dict(
        aug_corpus=PYTHON_AST_CORPUS,
        smooth_dist=1e-3,
        use_defvar_mask=True,
        add_abstractions_to_dsl=True,
    ),
    dict(
        aug_corpus=PYTHON_AST_CORPUS,
        smooth_dist=1e-3,
        use_defvar_mask=True,
        add_abstractions_to_dsl=True,
        use_smooth_mask=True,
    ),
    dict(smooth_dist=1e-3, use_defvar_mask=True, add_abstractions_to_dsl=True),
    dict(
        smooth_dist=1e-3,
        use_defvar_mask=True,
        add_abstractions_to_dsl=True,
        use_smooth_mask=True,
    ),
    dict(smooth_dist=1e-3, add_abstractions_to_dsl=True),
    dict(smooth_dist=1e-3, add_abstractions_to_dsl=True, use_smooth_mask=True),
]


def generate_var_map_fn(experiment):
    if experiment in {"canonicalized", "unified-scope"}:
        return unify_scope
    return None


def compress_corpus(
    corpus: List[ParsedAST],
    utility_fixed,
    utility_metavar,
    utility_symvar,
    include_size_by_symbol=True,
    include_dfa=True,
):
    size_by_symbol = f"-False" if not include_size_by_symbol else ""
    save_file = (
        "human-eval-compressed"
        + f"-{abs(utility_fixed)}-{abs(utility_metavar)}-{abs(utility_symvar)}"
        + size_by_symbol
        + ".json"
    )
    if os.path.exists(save_file):
        compressed = json.load(open(save_file, "r"))
        abstractions, rewritten_corpus = (
            compressed["abstractions"],
            compressed["compressed"],
        )
        return abstractions, rewritten_corpus

    root_states = None if include_dfa is False else ("E", "S", "seqS")
    abstractions, rewritten_corpus = run_julia_stitch(
        code=[sol.to_s_exp() for sol in corpus],
        stitch_jl_dir=JL_STITCH_DIR,
        iters=300,
        max_arity=1,
        root_states=root_states,
        metavariables_anywhere=not include_dfa,
        application_utility_fixed=utility_fixed,
        application_utility_metavar=utility_metavar,
        application_utility_symvar=utility_symvar,
        include_size_by_symbol=include_size_by_symbol,
    )
    json.dump(
        {"abstractions": abstractions, "compressed": rewritten_corpus},
        open(save_file, "w+"),
    )
    return abstractions, rewritten_corpus


def setup_corpus(run_corpus_compression, **kwargs):
    if run_corpus_compression:
        base_abstractions, compressed_corpus = compress_corpus(
            PYTHON_AST_CORPUS,
            **kwargs,
        )
        compressed_corpus = [ParsedAST.parse_s_expression(p) for p in compressed_corpus]
    else:
        base_abstractions, compressed_corpus = [], PYTHON_AST_CORPUS
    return base_abstractions, compressed_corpus


def multi_run(
    k,
    model,
    experiment,
    run_corpus_compression,
    strict_k,
    utility_fixed=-3,
    utility_metavar=-1,
    utility_symvar=-0.5,
    include_size_by_symbol=True,
    include_dfa=True,
    merge_dists=False,
    use_de_bruijn=False,
):
    if os.path.exists(COMPRESSED_SAVE_FILE):
        os.remove(COMPRESSED_SAVE_FILE)

    dataset = "apps"
    filename = "" if not run_corpus_compression else "compressed-corpus-"
    filename += f"{abs(utility_fixed)}-{abs(utility_metavar)}-{abs(utility_symvar)}"

    if not include_size_by_symbol:
        filename += f"-{include_size_by_symbol}"
    if merge_dists:
        filename += f"-merge-dists-smoothed-0.01"
    if not strict_k:
        filename += f"-all-qs"
    if use_de_bruijn:
        filename += f"-de-bruijn"

    assert model in {GPT_3, GPT_4}
    assert experiment in {"basic", "canonicalized", "unified-scope"}

    responses = GPT_3_RESPONSES if model == GPT_3 else GPT_4_RESPONSES
    results = GPT_3_RESULTS if model == GPT_3 else GPT_4_RESULTS
    base_abstractions, compressed_corpus = setup_corpus(
        run_corpus_compression,
        utility_fixed=utility_fixed,
        utility_metavar=utility_metavar,
        utility_symvar=utility_symvar,
        include_size_by_symbol=include_size_by_symbol,
        include_dfa=include_dfa,
    )

    runner = partial(
        get_all_likelihoods,
        k=k,
        experiment_type=experiment,
        gpt_response_file=responses,
        gpt_results_file=results,
        strict_k=strict_k,
        base_abstractions=base_abstractions,
        utility_fixed=utility_fixed,
        utility_metavar=utility_metavar,
        utility_symvar=utility_symvar,
        include_size_by_symbol=include_size_by_symbol,
        include_dfa=include_dfa,
        merge_dists=merge_dists,
    )
    save_dir = os.path.join(
        "results", dataset, model, f"k={k}", f"{experiment}-{filename}"
    )

    if not os.path.exists(save_dir):
        os.makedirs(save_dir)
    for i, args in enumerate(EXPERIMENTS):
        if run_corpus_compression:
            if not args.get("aug_corpus"):
                continue
            args["aug_corpus"] = compressed_corpus

        print(f"starting experiment {i+1}", flush=True)
        print("============================", flush=True)
        save_file = os.path.join(save_dir, f"{experiment}-{filename}-{i+1}.csv")
        print(save_file)
        if os.path.exists(save_file):
            raise FileExistsError
        runner(save_file=save_file, **args)
        print("============================", flush=True)
        print(f"ending experiment {i+1}\n", flush=True)
        break


if __name__ == "__main__":
    for k in [3, 5]:
        print(f"********************************")
        print(f"             k={k}              ")
        print(f"********************************")
        print("\n")
        for experiment in ["basic", "canonicalized", "unified-scope"]:
            print("running")
            multi_run(
                k=k,
                model=GPT_4,
                experiment=experiment,
                run_corpus_compression=False,
                strict_k=True,
                utility_fixed=-3,
                utility_metavar=-1,
                utility_symvar=-0.5,
                include_size_by_symbol=True,
                merge_dists=False,
            )
