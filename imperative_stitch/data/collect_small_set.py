import ast
import itertools
import json
import tqdm.auto as tqdm

from datasets import load_dataset

dataset = load_dataset("codeparrot/codeparrot-clean", split="train")

code = []
for i in tqdm.tqdm(itertools.count()):
    content = dataset[i]["content"]
    try:
        content = ast.unparse(ast.parse(content))
    except SyntaxError:
        continue
    code.append(content)
    if len(code) == 1000:
        break

with open("data/small_set.json", "w") as f:
    json.dump(code, f, indent=2)
