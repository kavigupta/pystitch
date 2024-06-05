import ast
import json
import os
import pandas as pd
import re

from functools import partial
from multiprocessing import Pool
from typing import Tuple

from imperative_stitch.parser.symbol import canonicalize_names
from imperative_stitch.compress.julia_stitch import run_julia_rewrite, run_julia_stitch
from imperative_stitch.parser.convert import python_to_s_exp

from .production_factory import Config
from .calculator import calculate
from ..utils.analysis_utils import (
    sort_programs,
    format_programs,
    strip_docstrings,
    unify_scope,
    remove_unused_abstractions,
)

FLUSH = True
NUM_PROCESSES = 16
CHUNK_SIZE = 30
COMPRESSED_SAVE_FILE = "tmp-compressed-save-file.json"
JL_STITCH_DIR = ""


def compress(
    wrong_programs: Tuple,
    correct_programs: Tuple,
    utility_fixed,
    utility_metavar,
    utility_symvar,
    base_abstractions,
    include_size_by_symbol=True,
    include_dfa=True,
    remove_unused_abstrs=False,
):
    root_states = None if include_dfa is False else ("E", "S", "seqS")
    s_exprs = stitch_s_exprs = [python_to_s_exp(sol) for sol in wrong_programs]
    target_s_exprs = [python_to_s_exp(target) for target in correct_programs]

    abstractions, programs = run_julia_stitch(
        code=stitch_s_exprs,
        stitch_jl_dir=JL_STITCH_DIR,
        iters=60,
        max_arity=1,
        root_states=root_states,
        metavariables_anywhere=not include_dfa,
        application_utility_fixed=utility_fixed,
        application_utility_metavar=utility_metavar,
        application_utility_symvar=utility_symvar,
        include_size_by_symbol=include_size_by_symbol,
    )

    if base_abstractions:

        def unify_fn_names(matchobj):
            new_number = matchobj.group(0).split("_")[-1]
            return f"fn_{int(new_number) + len(base_abstractions)}"

        for abst in abstractions:
            abst["body"] = re.sub("fn_[1-9][0-9]*", unify_fn_names, abst["body"])

    all_abstractions = base_abstractions + abstractions
    if base_abstractions:
        programs = run_julia_rewrite(
            s_exprs,
            abstrs,
            stitch_jl_dir=JL_STITCH_DIR,
            max_arity=1,
            root_states=root_states,
            metavariables_anywhere=not include_dfa,
            application_utility_fixed=utility_fixed,
            application_utility_metavar=utility_metavar,
            application_utility_symvar=utility_symvar,
            include_size_by_symbol=include_size_by_symbol,
        )
    if remove_unused_abstrs:
        corpus, output_abstrs = remove_unused_abstractions(programs, all_abstractions)
    else:
        corpus, output_abstrs = programs[:], all_abstractions[:]

    abstrs = [abst["body"] for abst in output_abstrs]
    if not abstrs:
        targets = target_s_exprs
    else:
        targets = []
        for i in range(0, len(target_s_exprs), CHUNK_SIZE):
            rewritten_targets = run_julia_rewrite(
                target_s_exprs[i : i + CHUNK_SIZE],
                abstrs,
                stitch_jl_dir=JL_STITCH_DIR,
                max_arity=1,
                root_states=root_states,
                metavariables_anywhere=not include_dfa,
                application_utility_fixed=utility_fixed,
                application_utility_metavar=utility_metavar,
                application_utility_symvar=utility_symvar,
                include_size_by_symbol=include_size_by_symbol,
            )
            targets += rewritten_targets[:]

    return output_abstrs, corpus, targets


def canonicalize(program):
    return ast.unparse(canonicalize_names(ast.parse(program)))


def setup(k, responses, results, q_num, experiment_type, strict_k):
    formatted, _ = format_programs(responses)
    responses = [strip_docstrings(sol) for sol in formatted]
    if experiment_type in {"canonicalized", "unified-scope"}:
        responses = [canonicalize(sol) for sol in responses]
    correct, wrong, idxs = sort_programs(responses, results[q_num])
    if strict_k:
        wrong = wrong[:k]
    return tuple(correct), tuple(wrong), tuple(idxs)


def setup_and_compress(
    gpt_entry,
    k,
    experiment_type,
    utility_fixed,
    utility_metavar,
    utility_symvar,
    base_abstractions,
    gpt_results,
    strict_k,
    include_size_by_symbol,
    include_dfa,
):
    q_num, responses = gpt_entry
    correct, wrong, idxs = setup(
        k, responses, gpt_results, q_num, experiment_type, strict_k
    )
    run_compression = partial(
        compress,
        correct_programs=correct,
        utility_fixed=utility_fixed,
        utility_metavar=utility_metavar,
        utility_symvar=utility_symvar,
        base_abstractions=base_abstractions,
        include_size_by_symbol=include_size_by_symbol,
        include_dfa=include_dfa,
    )

    if skip_question(k, correct, wrong, idxs, strict_k):
        print(f"skipping #{q_num}", flush=FLUSH)
        return ()

    print(f"compressing #{q_num}", flush=FLUSH)
    if strict_k:
        abstractions, programs, targets = run_compression(wrong_programs=wrong)
        return q_num, abstractions, list(programs), targets

    output = []
    for i in range(0, len(wrong), k):
        print(f"{q_num}-{len(output)}", flush=True)
        wrong_programs = wrong[i : i + k]
        if len(wrong_programs) != k or len(output) == 10:
            break
        assert len(wrong_programs) == k or len(wrong) < k
        abstractions, programs, targets = run_compression(wrong_programs=wrong_programs)
        output.append((f"{q_num}-{i // k}", abstractions, programs, targets))
    return output


def skip_question(k, correct_programs, wrong_programs, idxs, strict_k):
    if not correct_programs or not wrong_programs:
        return True
    return strict_k and idxs and idxs[0] < k


def get_compressed(setup_func, gpt_responses):
    if os.path.exists(COMPRESSED_SAVE_FILE):
        return json.load(open(COMPRESSED_SAVE_FILE, "r+"))
    with Pool(NUM_PROCESSES) as p:
        compressed = p.map(setup_func, gpt_responses.items())
    new_compressed = []
    for entry in compressed:
        if isinstance(entry, tuple):
            new_compressed.append(entry)
        else:
            assert isinstance(entry, list)
            new_compressed += entry
    compressed = new_compressed
    json.dump(compressed, open(COMPRESSED_SAVE_FILE, "w+"))
    print("got all compressed", flush=FLUSH)
    return compressed


def get_all_likelihoods(
    k,
    utility_fixed,
    experiment_type,
    gpt_response_file,
    gpt_results_file,
    save_file,
    utility_metavar=-1,
    utility_symvar=-0.5,
    expand_params=True,
    aug_corpus=[],
    base_abstractions=[],
    strict_k=True,
    include_size_by_symbol=True,
    include_dfa=True,
    **kwargs,
):
    data = {}

    gpt_responses = json.load(open(gpt_response_file, "r"))
    gpt_results = json.load(open(gpt_results_file, "r"))

    transform_vars = unify_scope if experiment_type == "unified-scope" else None

    setup_func = partial(
        setup_and_compress,
        k=k,
        experiment_type=experiment_type,
        utility_fixed=utility_fixed,
        utility_metavar=utility_metavar,
        utility_symvar=utility_symvar,
        base_abstractions=base_abstractions,
        gpt_results=gpt_results,
        strict_k=strict_k,
        include_size_by_symbol=include_size_by_symbol,
        include_dfa=include_dfa,
    )

    compressed = get_compressed(setup_func, gpt_responses)

    for compressed_items in compressed:
        if not compressed_items:
            continue

        q_num, abstractions, programs, targets = compressed_items

        print(f"calculating likelihoods for #{q_num}...", flush=FLUSH)
        likelihoods = run(
            targets,
            abstractions=abstractions,
            corpus=programs,
            canonicalize=transform_vars,
            aug_corpus=aug_corpus,
            config=Config(render_params=expand_params),
            **kwargs,
        )

        print(likelihoods, flush=FLUSH)
        data[q_num] = likelihoods

        df = pd.DataFrame({key: pd.Series(value) for key, value in data.items()})
        df.to_csv(save_file)

    print("\nALL DONE", flush=FLUSH)


def run(solutions, **kwargs):
    likelihood_func = partial(calculate, **kwargs)
    with Pool(NUM_PROCESSES) as p:
        results = p.map(likelihood_func, solutions)
    return results
