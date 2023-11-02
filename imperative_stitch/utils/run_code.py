import subprocess
import tempfile

import tqdm.auto as tqdm
from permacache import permacache, stable_hash


def normalize_output(output):
    """
    Normalize the output of a program, removing blank lines and trailing whitespace.
    """
    if output is None:
        return None
    output = output.split("\n")
    output = [line.strip() for line in output]
    output = [line for line in output if line]
    return "\n".join(output)


def passes_tests(code, inputs, outputs):
    for inp, out in list(zip(inputs, outputs)):
        py_out = run_python_with_timeout(code, inp)
        if py_out is None:
            return False
        out, py_out = normalize_output(out), normalize_output(py_out)
        if py_out != out:
            return False
    return True


def run_python_with_timeout(code, input, *, timeout=10):
    """
    Does the given code pass the given tests?
    """
    import signal

    def handler(signum, frame):
        raise TimeoutError()

    signal.signal(signal.SIGALRM, handler)
    signal.alarm(timeout)
    try:
        return run_python(code, input)
    except TimeoutError:
        return None


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
