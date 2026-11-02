(function_definition) @function.around
(function_definition body: (block) @function.inside)
(lambda) @function.around
(lambda body: (_) @function.inside)
(class_definition) @class.around
(class_definition body: (block) @class.inside)
(parameters (_) @parameter.inside @parameter.around)
(lambda_parameters (_) @parameter.inside @parameter.around)
(argument_list (_) @parameter.inside @parameter.around)
(comment) @comment.inside
(comment) @comment.around
