(function_item) @function.around
(function_item body: (block) @function.inside)
(closure_expression) @function.around
(closure_expression body: (_) @function.inside)
(struct_item) @class.around
(struct_item body: (_) @class.inside)
(enum_item) @class.around
(enum_item body: (_) @class.inside)
(trait_item) @class.around
(trait_item body: (_) @class.inside)
(impl_item) @class.around
(impl_item body: (_) @class.inside)
(parameters (_) @parameter.inside @parameter.around)
(closure_parameters (_) @parameter.inside @parameter.around)
(arguments (_) @parameter.inside @parameter.around)
(line_comment) @comment.inside
(line_comment) @comment.around
(block_comment) @comment.inside
(block_comment) @comment.around
