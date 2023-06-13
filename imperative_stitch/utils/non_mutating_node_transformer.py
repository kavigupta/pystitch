import ast
import copy


class NonMutatingNodeTransformer(ast.NodeTransformer):
    """
    Like ast.NodeTransformer, but does not mutate the original tree.
    """

    def generic_visit(self, node):
        # copied from https://github.com/python/cpython/blob/main/Lib/ast.py
        updated_node = copy.copy(node)
        for field, old_value in ast.iter_fields(node):
            if isinstance(old_value, list):
                new_values = []
                for value in old_value:
                    if isinstance(value, ast.AST):
                        value = self.visit(value)
                        if value is None:
                            continue
                        elif not isinstance(value, ast.AST):
                            new_values.extend(value)
                            continue
                    new_values.append(value)
                setattr(updated_node, field, new_values)
            elif isinstance(old_value, ast.AST):
                new_node = self.visit(old_value)
                if new_node is None:
                    delattr(updated_node, field)
                else:
                    setattr(updated_node, field, new_node)
        return updated_node
