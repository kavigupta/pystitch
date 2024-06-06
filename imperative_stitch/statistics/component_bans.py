import ast
from collections import defaultdict

import numpy as np
from python_graphs import control_flow

from imperative_stitch.analyze_program.ssa.banned_component import (
    BannedComponentError,
    check_banned_components,
)


def errors_for(entry):
    try:
        check_banned_components(ast.parse(entry.node))
        return []
    except BannedComponentError as e:
        return [e.component_type]


def all_errors(code):
    return sorted(
        {
            comp
            for entry in control_flow.get_control_flow_graph(
                ast.parse(code)
            ).get_enter_blocks()
            for comp in errors_for(entry)
        }
    )


def compute_statistics_each(errors_each):
    good = np.mean([not x for x in errors_each])
    causes_issue = defaultdict(int)
    for err in errors_each:
        for x in err:
            causes_issue[x] += 1
    return good, sorted(
        {k: v / len(errors_each) for k, v in causes_issue.items()}.items(),
        key=lambda x: -x[1],
    )
