import itertools
import json
import tempfile
import subprocess

import tqdm.auto as tqdm

from permacache import permacache, stable_hash
from datasets import load_dataset


def extract_from_data(datapoint, *, max_tests, max_solutions):
    """
    Extract runnable code from a datapoint.

    Returns a list of dicts with keys:
        name: str
        inputs: list[str]
        outputs: list[str]
        solution: str
    """
    name = datapoint["name"]
    tests = (
        datapoint["public_tests"],
        datapoint["private_tests"],
        datapoint["generated_tests"],
    )
    inputs, outputs = [], []
    for test in tests:
        inputs += test["input"]
        outputs += test["output"]
    inputs, outputs = inputs[:max_tests], outputs[:max_tests]
    solutions = [
        sol
        for lang, sol in zip(
            datapoint["solutions"]["language"], datapoint["solutions"]["solution"]
        )
        if lang == 3  # Python3
    ]
    solutions = solutions[:max_solutions]
    for i, sol in enumerate(tqdm.tqdm(solutions)):
        if not passes_tests(sol, inputs, outputs):
            continue
        yield dict(name=f"{name}_{i}", inputs=inputs, outputs=outputs, solution=sol)


def normalize_output(output):
    """
    Normalize the output of a program, removing blank lines and trailing whitespace.
    """
    output = output.split("\n")
    output = [line.strip() for line in output]
    output = [line for line in output if line]
    return "\n".join(output)


def passes_tests(code, inputs, outputs):
    """
    Does the given code pass the given tests?
    """
    for inp, out in list(zip(inputs, outputs)):
        py_out = run_python(code, inp)
        if py_out is None:
            return False
        out, py_out = normalize_output(out), normalize_output(py_out)
        if py_out != out:
            return False
    return True


@permacache(
    "imperative_stitch/data/runnable_code_set/run_python_2",
    key_function=dict(code=stable_hash, input=stable_hash),
)
def run_python(code, input):
    """
    Run the given python code with the given input.

    Returns the output of the program, or None if the program raised an exception.

    This is cached, so it's safe to call this function many times.
    """
    with tempfile.NamedTemporaryFile(suffix=".py") as f:
        f.write(code.encode("utf-8"))
        f.flush()
        try:
            z = subprocess.check_output(
                ["python3", f.name], input=input.encode("utf-8")
            )
        except subprocess.CalledProcessError as e:
            return None
        return z.decode("utf-8")


@permacache(
    "imperative_stitch/data/runnable_code_set/runnable_code_dataset",
)
def runnable_code_dataset(
    *, amount, max_solutions_per_datapoint, max_tests_per_datapoint
):
    """
    Load the runnable code dataset.

    Args:
        max_solutions_per_datapoint: int
            The maximum number of solutions to extract from each datapoint.
        max_tests_per_datapoint: int
            The maximum number of tests to include for each datapoint.

    Returns a list of dicts with keys:
        name: str
        inputs: list[str]
        outputs: list[str]
        solution: str
    """
    dataset = load_dataset("deepmind/code_contests", split="train")
    result = []
    for i in itertools.count():
        data = dataset[i]
        data = list(
            extract_from_data(
                data,
                max_solutions=max_solutions_per_datapoint,
                max_tests=max_tests_per_datapoint,
            )
        )
        result += data
        print(len(result))
        if len(result) >= amount:
            break
    return result[:amount]


if __name__ == "__main__":
    with open("data/small_set_runnable_code.json", "w") as f:
        json.dump(
            runnable_code_dataset(
                amount=300, max_solutions_per_datapoint=10, max_tests_per_datapoint=10
            ),
            f,
            indent=2,
        )
