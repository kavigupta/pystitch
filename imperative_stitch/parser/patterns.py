import re

VARIABLE_PATTERN = re.compile(r"var-(?P<name>[%#\?]\w+)(~.*)?")
