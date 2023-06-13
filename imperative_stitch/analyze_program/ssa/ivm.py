from abc import ABC, abstractmethod
from ast import AST
from dataclasses import dataclass


class Origin(ABC):
    def replaceable_without_propagating(self, other):
        """
        Whether this origin can be replaced by another origin without propagating
        the replacement to the children.
        """
        return self == other

    def remap(self, renaming_map):
        """
        Remap the origin using the renaming map.
        """
        return self

    @abstractmethod
    def initial(self):
        """
        Whether this is an initial value.
        """
        pass


@dataclass
class Uninitialized(Origin):
    def initial(self):
        return True


@dataclass
class Argument(Origin):
    def initial(self):
        return True


@dataclass
class DefinedIn(Origin):
    site: AST

    def initial(self):
        return False


@dataclass
class Phi(Origin):
    parents: list

    def replaceable_without_propagating(self, other):
        return isinstance(other, Phi)

    def remap(self, renaming_map):
        return Phi(sorted({renaming_map[x] for x in self.parents}))

    def initial(self):
        return False


class SSAVariableIntermediateMapping:
    """
    A mapping from identifiers to an Origin object

    Fields:
        original_symbol_of: A mapping from SSA variables to their original symbols.
        parents_of: A mapping from SSA variables to their parents.
            A parent is either a list of numbers (phi values)
            or a list containing a string "uninitialized" (not initialized)
            or a list containing a tuple ("init", astn) (initialized at that site).
    """

    def __init__(self):
        self.original_symbol_of = {}
        self.parents_of = {}

    def fresh_variable(self, original_symbol, parents):
        var = len(self.original_symbol_of)
        self.original_symbol_of[var] = original_symbol
        self.parents_of[var] = parents
        return var

    def fresh_variable_if_needed(self, original_symbol, parents, current):
        if current is not None and self.original_symbol_of[current] == original_symbol:
            if self.parents_of[current] == parents:
                return current
            if self.parents_of[current].replaceable_without_propagating(parents):
                self.parents_of[current] = parents
                return current
        return self.fresh_variable(original_symbol, parents)

    def arguments_map(self):
        """
        Returns a map from the symbol to the variable id
            for all arguments.
        """
        return {
            self.original_symbol_of[var]: var
            for var, parents in self.parents_of.items()
            if parents == Argument()
        }

    def initials(self):
        """
        Returns the variables that are initialized at the beginning of the function.
        """
        return [var for var, origin in self.parents_of.items() if origin.initial()]

    def export_parents(self, renaming_map):
        """
        Export the parents of each variable using the renaming map.
        """
        result = {
            renaming_map[node]: origin.remap(renaming_map)
            for node, origin in self.parents_of.items()
        }
        return result
