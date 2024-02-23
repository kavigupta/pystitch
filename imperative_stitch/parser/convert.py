from imperative_stitch.parser.parsed_ast import ParsedAST


def python_to_s_exp(code, **kwargs):
    """
    Converts python code to an s-expression.
    """
    return ParsedAST.parse_python_module(code).to_s_exp(**kwargs)


def s_exp_to_python(code):
    """
    Converts an s expression to python code.
    """
    return ParsedAST.parse_s_expression(code).to_python()
