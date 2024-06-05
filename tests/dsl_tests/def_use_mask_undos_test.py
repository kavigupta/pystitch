import copy
import unittest

import neurosym as ns

from imperative_stitch.compress.abstraction import Abstraction

from imperative_stitch.data.stitch_output_set import load_stitch_output_set
from imperative_stitch.parser import converter
from imperative_stitch.utils.def_use_mask_extension.abstraction_handler import (
    VARIABLE_REGEX,
    CollectingHandler,
)
from tests.utils import expand_with_slow_tests

from .utils import fit_to


class DefUseMaskAbstractionUndosTest(unittest.TestCase):
    def setUp(self):
        CollectingHandler.disable_arity_check = True

    def tearDown(self):
        CollectingHandler.disable_arity_check = False

    def get_handler_except_mask(self, handler):
        result = {
            k: v
            for k, v in handler.__dict__.items()
            if k not in {"mask", "config", "_mask_copy"}
        }
        if "traverser" in result:
            result["traverser"] = self.get_handler_except_mask(result["traverser"])
        if "underlying_handler" in result:
            result["underlying_handler"] = self.get_handler_except_mask(
                result["underlying_handler"]
            )
        if "children" in result:
            result["children"] = {
                id: self.get_handler_except_mask(child)
                for id, child in result["children"].items()
            }
        return result

    def get_handlers_except_mask(self, mask):
        handlers = mask.masks[-1].handlers
        return [self.get_handler_except_mask(handler) for handler in handlers]

    def annotate_program(self, program, abstrs, with_undo, with_undo_exit):
        def replace_node_midstream(s_exp, mask, position, alts):
            if with_undo:
                for alt in alts:
                    if VARIABLE_REGEX.match(mask.masks[-1].id_to_name(alt)):
                        continue
                    print("handlers", mask.masks[-1].handlers)
                    print("before entry", self.get_handlers_except_mask(mask))
                    last_handler = copy.deepcopy(self.get_handlers_except_mask(mask))
                    undo = mask.on_entry(position, alt)
                    print("handlers", mask.masks[-1].handlers)
                    print("after entry", self.get_handlers_except_mask(mask))
                    undo()
                    print("after undo entry", self.get_handlers_except_mask(mask))
                    self.assertEqual(
                        last_handler,
                        self.get_handlers_except_mask(mask),
                    )
            if with_undo_exit:
                for alt in alts:
                    if VARIABLE_REGEX.match(mask.masks[-1].id_to_name(alt)):
                        continue
                    undo_entry = mask.on_entry(position, alt)
                    # print("*" * 80)
                    # print("handlers", mask.masks[-1].handlers)
                    last_handler = copy.deepcopy(self.get_handlers_except_mask(mask))
                    # print("copy", last_handler)
                    undo_exit = mask.on_exit(position, alt)
                    # print("after exit", self.get_handlers_except_mask(mask))
                    undo_exit()
                    # print(
                    #     "after undo exit",
                    #     self.get_handlers_except_mask(mask),
                    # )
                    self.assertEqual(
                        last_handler,
                        self.get_handlers_except_mask(mask),
                    )
                    undo_entry()

            return s_exp

        dfa, _, fam, _ = fit_to(
            [program],
            parser=converter.s_exp_to_python_ast,
            include_type_preorder_mask=False,
            abstrs=abstrs,
        )
        td = fam.tree_distribution_skeleton
        result = list(
            ns.collect_preorder_symbols(
                ns.to_type_annotated_ns_s_exp(
                    converter.s_exp_to_python_ast(program), dfa, "M"
                ),
                fam.tree_distribution_skeleton,
                replace_node_midstream=replace_node_midstream,
            )
        )
        result = [
            (ns.render_s_expression(s_exp), [td.symbols[i][0] for i in alts])
            for s_exp, alts, _ in result
        ]
        # print(result)
        return result

    def assertUndoHasNoEffect(self, program, abstrs):
        self.maxDiff = None
        without_undo = self.annotate_program(
            program, abstrs, with_undo=False, with_undo_exit=False
        )
        with_undo = self.annotate_program(
            program, abstrs, with_undo=True, with_undo_exit=False
        )
        with_undo_exit = self.annotate_program(
            program, abstrs, with_undo=False, with_undo_exit=True
        )
        self.assertEqual(with_undo, without_undo)
        self.assertEqual(with_undo_exit, without_undo)

    def check_use_mask(self, x):
        x = copy.deepcopy(x)
        abstractions = [
            Abstraction.of(name=f"fn_{it + 1}", **abstr)
            for it, abstr in enumerate(x["abstractions"])
        ]
        for _, rewritten in zip(x["code"], x["rewritten"]):
            print("rewritten", rewritten)
            print("abstractions", abstractions)
            self.assertUndoHasNoEffect(rewritten, abstractions)

    @expand_with_slow_tests(len(load_stitch_output_set()), 10)
    def test_realistic_with_abstractions(self, i):
        self.check_use_mask(load_stitch_output_set()[i])
