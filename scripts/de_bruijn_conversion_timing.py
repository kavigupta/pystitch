import time
from imperative_stitch.utils.classify_nodes import export_dfa
from tests.dsl_tests.canonicalize_de_bruijn_test import LikelihoodDeBruijnTest, parse_and_check
from tests.utils import small_set_runnable_code_examples


programs = []
for x in small_set_runnable_code_examples():
    pa, se = parse_and_check(x["solution"], do_actual_check=False)
    if se is not None:
        programs.append(pa)
        if len(programs) == 200:
            break
start = time.time()
LikelihoodDeBruijnTest().fit_dsl(
    *programs,
    max_explicit_dbvar_index=2,
    abstrs=(),
    dfa=export_dfa(),
)
end = time.time()
print(end-start)
