from imperative_stitch.compress.julia_stitch import Abstraction


def inject_pragmas(rewritten_s_exp, abstraction: Abstraction):
    """
    Convert the given rewritten s-expression into one that contains the original body
        of the abstraction, but wrapped in the __start_extract__ and __end_extract__ pragmas.
    """

    sites = find_sites(rewritten_s_exp, abstraction)


def find_sites(s_exp, abstraction: Abstraction):
    """
    Find all sites in the given s-expression that match the given abstraction.

    If it is a subseq abstraction, then finds the sites of the /splice.

    Yields the sites as nodes
    """
