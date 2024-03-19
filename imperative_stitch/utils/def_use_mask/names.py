import re

NAME_REGEX = re.compile(
    r"const-(?P<typ>&)(?P<name>\w+|\*):(?P<scope>\d+)~(Name|NameStr|NullableNameStr)"
)
GLOBAL_REGEX = re.compile(
    r"const-(?P<typ>g)_(?P<name>\w+|\*)~(Name|NameStr|NullableNameStr)"
)


def match_either(s):
    return NAME_REGEX.match(s) or GLOBAL_REGEX.match(s)
