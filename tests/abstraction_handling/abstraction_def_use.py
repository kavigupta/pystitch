import unittest
from textwrap import dedent

from imperative_stitch.compress.abstraction import Abstraction
from imperative_stitch.parser.parsed_ast import ParsedAST
from imperative_stitch.utils.classify_nodes import export_dfa
from imperative_stitch.utils.export_as_dsl import DSLSubset, create_dsl


class AbstractionRenderingTest(unittest.TestCase):
    def test_fn_1_def_use(self):
        pass
