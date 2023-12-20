import json
import os

import fire
from datasets import load_dataset

from imperative_stitch.to_s import python_to_s_exp


def compression_testing_code(amount):
    dset = load_dataset("deepmind/code_contests", split="train")
    sets = []
    for datum in dset:
        py3s = [
            sol
            for sol, lang in zip(
                datum["solutions"]["solution"], datum["solutions"]["language"]
            )
            if lang == 3
        ]
        if len(py3s) > 3:
            sets.append(py3s)
        if len(sets) > amount:
            break
    return sets


def produce_julia_tests(jl_path):
    test_out_folder = os.path.join(jl_path, "data", "imperative_realistic")
    code = compression_testing_code(100)
    code = [x[:10] for x in code]
    code = [x for x in code if len(json.dumps(x)) < 10**4]
    assert len(code) >= 10
    code = code[:10]
    for i, tests in enumerate(code):
        tests = [python_to_s_exp(x) for x in tests]
        p = os.path.join(test_out_folder, str(i) + ".json")
        with open(p, "w") as f:
            json.dump(tests, f)

        with open(p + "-args.json", "w") as f:
            json.dump(
                [
                    {
                        "dfa": "data_for_testing/dfa_imp.json",
                        "size_by_symbol": "data_for_testing/size_by_symbol.json",
                        "application_utility_fixed": -3,
                        "application_utility_metavar": -1,
                        "application_utility_choicevar": -1.01,
                        "application_utility_symvar": -0.5,
                        "match_sequences": True,
                    }
                ],
                f,
                indent=2,
            )


if __name__ == "__main__":
    import fire

    fire.Fire(produce_julia_tests)
