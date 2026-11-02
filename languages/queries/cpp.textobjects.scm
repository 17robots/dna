(function_definition) @function.around
(function_definition body: (compound_statement) @function.inside)
(lambda_expression) @function.around
(lambda_expression body: (compound_statement) @function.inside)
(class_specifier body: (_)) @class.around
(class_specifier body: (_) @class.inside)
(struct_specifier body: (_)) @class.around
(struct_specifier body: (_) @class.inside)
(union_specifier body: (_)) @class.around
(union_specifier body: (_) @class.inside)
(enum_specifier body: (_)) @class.around
(enum_specifier body: (_) @class.inside)
(parameter_list (_) @parameter.inside @parameter.around)
(argument_list (_) @parameter.inside @parameter.around)
(comment) @comment.inside
(comment) @comment.around
