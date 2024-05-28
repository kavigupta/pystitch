"""
There are three representations of a python program.

    1. actual python code, as a string. E.g., "x = 2"
    2. the PythonAST representation we use
    3. s-expressions for stitch. E.g., "(Assign (list (Name &x:0 Store)) (Constant i2 None) None)"
"""

from .python_ast import PythonAST
