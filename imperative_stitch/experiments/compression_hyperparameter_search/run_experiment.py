from tqdm.contrib.concurrent import process_map

from .datasets import datasets
from .run_stitch import run_stitch_with_hyperparameters


def run_experiment_up_to_seed(num_seeds, hypers_for_seed, *, skip_missing):
    data = datasets()

    arguments = [
        (k, seed, hypers_for_seed(seed), skip_missing)
        for seed in range(num_seeds)
        for k in data
    ]
    results_flat = process_map(run_experiment, arguments, max_workers=16)
    results_flat = {
        (k, seed): result for (k, seed, _, _), result in zip(arguments, results_flat)
    }

    results = []
    for seed in range(num_seeds):
        result = {}
        for k in data:
            result[k] = results_flat[k, seed]
        results.append(result)
    return results


def run_experiment(k_seed_hypers_skip_missing):
    k, seed, hypers, skip_missing = k_seed_hypers_skip_missing
    data = datasets()
    kwargs = dict(
        dataset=[v for _, v in sorted(data[k].items())],
        stitch_jl_dir="../Stitch.jl/",
        iters=10,
        **hypers,
        print_before_after=f"{k} with seed {seed}",
    )
    if skip_missing and not run_stitch_with_hyperparameters.cache_contains(**kwargs):
        print(f"Skipping {k} with seed {seed}")
        return None
    return run_stitch_with_hyperparameters(**kwargs)


def vary_min_num_matches():
    minimum_number_matches = [2, 3, 4, 5, 10, 20]

    def hypers(seed):
        return {
            "max_arity": 3,
            "minimum_number_matches": minimum_number_matches[seed],
            "application_utility_metavar": -1.5,
            "application_utility_symvar": -0.2,
            "application_utility_fixed": -3,
        }

    return len(minimum_number_matches), hypers


if __name__ == "__main__":
    run_experiment_up_to_seed(*vary_min_num_matches(), skip_missing=False)
