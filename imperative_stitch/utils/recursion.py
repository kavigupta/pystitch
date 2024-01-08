import sys


class recursionlimit:
    # https://stackoverflow.com/a/50120316/1549476
    def __init__(self, limit):
        self.limit = limit

    def __enter__(self):
        # pylint: disable=attribute-defined-outside-init
        self.old_limit = sys.getrecursionlimit()
        sys.setrecursionlimit(self.limit)

    def __exit__(self, _1, _2, _3):
        sys.setrecursionlimit(self.old_limit)


def no_recursionlimit():
    # biggest possible recursion limit, can't be set higher
    # because it is a signed 32-bit integer
    return recursionlimit(2**31 - 1)


def limit_to_size(code):
    return recursionlimit(max(1500, len(code)))
