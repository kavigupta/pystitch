import json
import os
import subprocess


def run_julia_stitch(code, *, stitch_jl_dir, iters):
    result = subprocess.run(
        [
            "julia",
            "--project=" + stitch_jl_dir,
            os.path.join(stitch_jl_dir, "src/cli.jl"),
            f"--iterations={iters}",
        ],
        input=json.dumps(code).encode("utf-8"),
        capture_output=True,
    ).stdout
    *_, tildes, result, newline = result.decode("utf-8").split("\n")
    assert tildes == "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~" and not newline
    result = json.loads(result)
    return result
