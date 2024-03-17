import re

NAME_REGEX = re.compile(r"const-&(\w+):(\d+)~(Name|NameStr|NullableNameStr)")
GLOBAL_REGEX = re.compile(r"const-g_(\w+)~(Name|NameStr|NullableNameStr)")
