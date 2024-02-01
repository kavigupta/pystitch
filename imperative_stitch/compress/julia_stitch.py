import json
import os
import shlex
import subprocess

from imperative_stitch.utils.classify_nodes import export_dfa

# a, b = f(c, d)
# (Assign
#     (list (Tuple (list (Name &a:0 Store) (Name &b:0 Store)) Store))
#     (Call (Name &f:0 Load) (list (Name &c:0 Load) (Name &d:0 Load)) nil)
#     None
# )
# sizeof
#     = assign_size + n_returns * sym_size + call_size + fn_name + n_returns * sym_size
#     = assign_size + call_size + fn_name + 2 * n_returns * sym_size


def run_julia_stitch(
    code,
    *,
    stitch_jl_dir,
    iters,
    max_arity,
    quiet=True,
    application_utility_metavar=-1,
    application_utility_symvar=-0.5,
    application_utility_fixed=-3,  # see reasoning above
    include_dfa=True,
    root_states=("E", "S", "seqS"),
    metavariable_statements=True,
):
    size_by_symbol = {
        "Module": 0.0,
        "Name": 0.0,
        "Load": 0.0,
        "Store": 0.0,
        "None": 0.0,
        "list": 0.0,
        "nil": 0.0,
        "/seq": 0.0,
        "Constant": 0.0,
        "Attribute": 0.0,
    }
    with open("data/dfa.json", "w") as f:
        json.dump(export_dfa(), f, indent=2)
    cmd = [
        "julia",
        "--project=" + stitch_jl_dir,
        os.path.join(stitch_jl_dir, "src/cli.jl"),
        f"--iterations={iters}",
        f"--max-arity={max_arity}",
        *([f"--dfa={os.path.abspath('data/dfa.json')}"] if include_dfa else []),
        f"--size-by-symbol={json.dumps(size_by_symbol)}",
        f"--application-utility-fixed={application_utility_fixed}",
        f"--application-utility-metavar={application_utility_metavar}",
        f"--application-utility-symvar={application_utility_symvar}",
        f"--dfa-valid-root-states={json.dumps(list(root_states))}",
        *(
            []
            if metavariable_statements
            else ["--dfa-metavariable-disallow-S", "--dfa-metavariable-disallow-seqS"]
        ),
    ]
    if not quiet:
        temp_txt = os.path.join(stitch_jl_dir, "temp.txt")
        with open(temp_txt, "w") as f:
            f.write(json.dumps(code))
        print("Run the following command to debug:")
        print(" ".join([shlex.quote(x) for x in cmd]) + " < " + temp_txt)
    abstractions = subprocess.run(
        cmd,
        input=json.dumps(code).encode("utf-8"),
        capture_output=True,
        check=False,
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
