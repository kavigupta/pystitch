from abc import ABC, abstractmethod
from ast import AST
from dataclasses import dataclass


class Origin(ABC):
    def replaceable_without_propagating(self, current, other):
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

    @abstractmethod
    def initialized(self):
        """
        Whether this is an initialized value.
        """
        pass

    def without_parent(self, parent):
        return self

    def reduce_if_possible(self):
        return None


@dataclass(eq=True, frozen=True)
class Uninitialized(Origin):
    def initial(self):
        return True

    def initialized(self):
        return False


@dataclass(eq=True, frozen=True)
class Argument(Origin):
    def initial(self):
        return True

    def initialized(self):
        return True


@dataclass(eq=True, frozen=True)
class DefinedIn(Origin):
    site: AST

    def initial(self):
        return False

    def initialized(self):
        return True


@dataclass(eq=True, frozen=True)
class Phi(Origin):
    node: AST
    parents: tuple

    def replaceable_without_propagating(self, current, other):
        return isinstance(other, Phi)

    def remap(self, renaming_map):
        return Phi(
            self.node, tuple(sorted({renaming_map.get(x, x) for x in self.parents}))
        )

    def initial(self):
        return False

    def initialized(self):
        return True

    def without_parent(self, parent):
        if parent not in self.parents:
            return self
        return Phi(self.node, tuple(x for x in self.parents if x != parent))

    def reduce_if_possible(self):
        if len(self.parents) == 1:
            return self.parents[0]
        return None


@dataclass(eq=True, frozen=True)
class Gamma(Origin):
    node: AST
    closed: tuple

    def replaceable_without_propagating(self, current, other):
        raise NotImplementedError

    def remap(self, renaming_map):
        return Gamma(
            self.node,
            tuple(sorted({renaming_map[x] for x in self.closed})),
        )

    def initial(self):
        return False

    def initialized(self):
        return True


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
        var = 1 + max(self.original_symbol_of) if self.original_symbol_of else 0
        self.original_symbol_of[var] = original_symbol
        self.parents_of[var] = parents
        return var

    def fresh_variable_if_needed(self, original_symbol, parents, current):
        if current is not None and self.original_symbol_of[current] == original_symbol:
            print("PARENTS OF", self.parents_of[current], parents)
            if self.parents_of[current] == parents:
                return current
            if self.parents_of[current].replaceable_without_propagating(
                current, parents
            ):
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
        result = {}
        for node, origin in self.parents_of.items():
            if node in renaming_map:
                result[renaming_map[node]] = origin.remap(renaming_map)
        return result

    def clean(self):
        """
        Remove all self-parented variable references.
        """

        renamer = {}
        while True:
            done = True
            for var in self.parents_of:
                replacement = self.parents_of[var].without_parent(var)
                if replacement is not self.parents_of[var]:
                    self.parents_of[var] = replacement
                    done = False
                    break

            for var in self.parents_of:
                replacement = self.parents_of[var].reduce_if_possible()
                if replacement is not None:
                    self.remap(var, replacement)
                    renamer[var] = replacement
                    done = False
                    break
            if done:
                break
        return resolve_pointers(renamer)

    def remap(self, old, new):
        """
        Replace all references to old with new.
        """
        assert self.original_symbol_of[new] == self.original_symbol_of[old]
        del self.original_symbol_of[old]
        del self.parents_of[old]
        for var, origin in self.parents_of.items():
            self.parents_of[var] = origin.remap({old: new})


def resolve_pointers(renamer):
    """
    If a -> b and b -> c then replace with a -> c and b -> c.
    """

    def resolve(x):
        while x in renamer:
            x = renamer[x]
        return x

    return {x: resolve(y) for x, y in renamer.items()}


def compute_ultimate_origins(origin_of):
    """
    For each variable list all the variables that are the ultimate origin of it.

    An ultimate origin is either the origin of a variable or, if the variable's origin
        is a Phi node, the ultimate origin of one of the variables that the Phi node
        depends on.
    """
    # there's probably a faster way to do this but this is fast enough for now
    ultimate_origins = {}
    for var in origin_of:
        ultimate_origins[var] = set()
        seen = set()
        fringe = [var]
        while fringe:
            to_process = fringe.pop()
            if to_process in seen:
                continue
            seen.add(to_process)
            if isinstance(origin_of[to_process], Phi):
                fringe.extend(origin_of[to_process].parents)
            ultimate_origins[var].add(origin_of[to_process])
    return ultimate_origins
