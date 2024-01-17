import json

import tqdm
from permacache import permacache, stable_hash

from imperative_stitch.compress.julia_stitch import run_julia_stitch
from imperative_stitch.data.compression_testing_code import compression_testing_code
from imperative_stitch.parser import python_to_s_exp


@permacache(
    "imperative_stitch/data/stitch_output_set/run_stitch_cached_3",
    key_function=dict(c=stable_hash),
)
def run_stitch_cached(c):
    return run_julia_stitch(
        c,
        stitch_jl_dir="../Stitch.jl/",
        iters=1,
        application_utility_symvar=-0.5,
        max_arity=4,
        quiet=False,
    )


@permacache(
    "imperative_stitch/data/stitch_output_set/stitch_output_set_5",
)
def stitch_output_set(amount):
    sets = compression_testing_code(amount * 10)
    sets = [x[:10] for x in sets]

    results = []

    pbar = tqdm.tqdm(total=amount)

    for s in sets:
        if len(json.dumps(s)) > 5000:
            continue
        c = [python_to_s_exp(code) for code in s]

        abstractions, rewritten = run_stitch_cached(c)

        result = dict(
            code=c,
            abstractions=abstractions,
            rewritten=rewritten,
        )

        results.append(result)
        pbar.update(1)

        if len(results) >= amount:
            pbar.close()
            break

    return results


if __name__ == "__main__":
    small = stitch_output_set(10)
    with open("data/stitch_output_set_small.json", "w") as f:
        json.dump(small, f, indent=2)

    full = stitch_output_set(100)
    with open("data/stitch_output_set.json", "w") as f:
        json.dump(full, f, indent=2)
