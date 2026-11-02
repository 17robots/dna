(function_definition) @function.around
(function_definition body: (compound_statement) @function.inside)
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
