import numpy as np

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.compress.manipulate_abstraction import abstraction_calls_to_stubs


def wall_time(res):
    if res is None:
        return np.inf
    return res[-1]


def s_exp_compression(res):
    if res is None:
        return np.nan
    (amounts, *_), _ = res
    return amounts[0] / amounts[-1]


def print_out_abstractions(seed, result):
    for k in result:
        if result[k] is None:
            continue
        (_, abstrs, rewr), _ = result[k]
        abstrs = [Abstraction.of(name=f"fn_{i}", **x) for i, x in enumerate(abstrs, 1)]
        abstrs_d = {abstr.name: abstr for abstr in abstrs}
        if not abstrs:
            continue
        print("*" * 80)
        print(seed, k)
        for abstr in abstrs:
            print(" " * 10, "*" * 40)
            counts = [x.count(abstr.name) for x in rewr]
            print(" " * 10, abstr.name, "::", sum(counts), [x for x in counts if x])
            code = abstraction_calls_to_stubs(
                abstr.body_with_variable_names(), abstrs_d
            ).to_python()
            code = code.replace("\n", "\n" + " " * 11)
            print(" " * 10, code)
