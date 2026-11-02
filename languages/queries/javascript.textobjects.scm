(function_declaration) @function.around
(function_declaration body: (statement_block) @function.inside)
(function_expression) @function.around
(function_expression body: (statement_block) @function.inside)
(arrow_function) @function.around
(arrow_function body: (_) @function.inside)
(method_definition) @function.around
(method_definition body: (statement_block) @function.inside)
(generator_function_declaration) @function.around
(generator_function_declaration body: (statement_block) @function.inside)
(class_declaration) @class.around
(class_declaration body: (class_body) @class.inside)
(class) @class.around
(class body: (class_body) @class.inside)
(formal_parameters (_) @parameter.inside @parameter.around)
(arguments (_) @parameter.inside @parameter.around)
(comment) @comment.inside
(comment) @comment.around
