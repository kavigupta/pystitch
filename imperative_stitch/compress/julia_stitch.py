import json
import os
import subprocess


def run_julia_stitch(code, *, stitch_jl_dir, iters, max_arity, quiet=True):
    cmd = [
        "julia",
        "--project=" + stitch_jl_dir,
        os.path.join(stitch_jl_dir, "src/cli.jl"),
        f"--iterations={iters}",
        f"--max-arity={max_arity}",
    ]
    if not quiet:
        temp_txt = os.path.join(stitch_jl_dir, "temp.txt")
        with open(temp_txt, "w") as f:
            f.write(json.dumps(code))
        print("Run the following command to debug:")
        print(" ".join(cmd) + " < " + temp_txt)
    abstractions = subprocess.run(
        cmd,
        input=json.dumps(code).encode("utf-8"),
        capture_output=True,
    ).stdout
    abstractions = abstractions.decode("utf-8")
    if not quiet:
        print(abstractions)
    *_, tildes1, abstractions, tildes2, rewritten, newline = abstractions.split("\n")
    assert tildes1 == "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
    assert tildes2 == "~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~"
    assert newline == ""
    abstractions = json.loads(abstractions)
    rewritten = json.loads(rewritten)
    return abstractions, rewritten
