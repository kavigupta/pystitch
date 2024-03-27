def defining_statement_handlers():
    # pylint: disable=cyclic-import
    from .chained_definitions_handler import chained_definition_handlers
    from .defining_construct_handler import defining_construct_handler
    from .defining_statement_handler import (
        AssignHandler,
        ForHandler,
        ImportFromHandler,
        ImportHandler,
        LambdaHandler,
    )

    return {
        x.name: x
        for x in [
            AssignHandler,
            ImportHandler,
            ImportFromHandler,
            ForHandler,
            LambdaHandler,
            *defining_construct_handler,
            *chained_definition_handlers,
        ]
    }
