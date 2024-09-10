from .datasets import datasets
from .hyperparameters import sample_hyperparameters
from .run_stitch import run_stitch_with_hyperparameters


def run_experiment_up_to_seed(num_seeds):
    data = datasets()
    results = []
    for seed in range(num_seeds):
        result = {}
        for k in data:
            print(f"Running {k} with seed {seed}")
            result[k] = run_stitch_with_hyperparameters(
                [v for _, v in sorted(data[k].items())],
                "../Stitch.jl/",
                iters=10,
                **sample_hyperparameters(0),
            )
        results.append(result)


if __name__ == "__main__":
    run_experiment_up_to_seed(10)
