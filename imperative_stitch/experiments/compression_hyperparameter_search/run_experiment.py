from tqdm.contrib.concurrent import process_map

from .datasets import datasets
from .hyperparameters import sample_hyperparameters
from .run_stitch import run_stitch_with_hyperparameters


def run_experiment_up_to_seed(num_seeds):
    data = datasets()

    arguments = [(k, seed) for seed in range(num_seeds) for k in data]
    results_flat = process_map(run_experiment, arguments, max_workers=16)
    results_flat = dict(zip(data, results_flat))

    results = []
    for seed in range(num_seeds):
        result = {}
        for k in data:
            result[k] = results_flat[k, seed]
        results.append(result)
    return results


def run_experiment(k_seed):
    k, seed = k_seed
    data = datasets()
    result = run_stitch_with_hyperparameters(
        [v for _, v in sorted(data[k].items())],
        "../Stitch.jl/",
        iters=10,
        **sample_hyperparameters(seed),
        print_before_after=f"{k} with seed {seed}",
    )
    return result


if __name__ == "__main__":
    run_experiment_up_to_seed(10)
