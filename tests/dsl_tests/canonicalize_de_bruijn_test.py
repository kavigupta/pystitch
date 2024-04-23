import ast
import copy
import sys
import unittest

import neurosym as ns

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.data.stitch_output_set import (
    load_stitch_output_set,
    load_stitch_output_set_no_dfa,
)
from imperative_stitch.parser.parsed_ast import NodeAST, ParsedAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.def_use_mask.mask import DefUseChainPreorderMask
from imperative_stitch.utils.def_use_mask.names import match_either
from tests.dsl_tests.dsl_test import fit_to
from tests.utils import (
    cwq,
    expand_with_slow_tests,
    load_annies_compressed_individual_programs,
    small_set_runnable_code_examples,
)


class DefUseMaskTestGeneric(unittest.TestCase):

    def test_canonicalize_de_bruijn(self):
        programs = ["x = 2; y = x + 1; z = x + y; x = 3"]
        programs = [ParsedAST.parse_python_module(program) for program in programs]
        dfa = export_dfa()
        sexp = programs[0].to_type_annotated_de_bruijn_ns_s_exp(
            dfa, "M", de_bruijn_limit=2
        )
        self.maxDiff = None
        expected = """
        (Module~M 
            (/seq~seqS~4
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-0) (Store~Ctx)))
                    (Constant~E (const-i2~Const) (const-None~ConstKind))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-0) (Store~Ctx)))
                    (BinOp~E (Name~E (dbvar-1) (Load~Ctx)) (Add~O) (Constant~E (const-i1~Const) (const-None~ConstKind)))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-0) (Store~Ctx)))
                    (BinOp~E (Name~E (dbvar-2) (Load~Ctx)) (Add~O) (Name~E (dbvar-1) (Load~Ctx)))
                    (const-None~TC))
                (Assign~S
                    (list~_L_~1 (Name~L (dbvar-successor (dbvar-2)) (Store~Ctx)))
                    (Constant~E (const-i3~Const) (const-None~ConstKind))
                    (const-None~TC)))
            (list~_TI_~0))
        """
        self.assertEqual(
            ns.render_s_expression(sexp),
            ns.render_s_expression(ns.parse_s_expression(expected)),
        )
