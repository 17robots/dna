(function_declaration) @function.around
(function_declaration body: (block) @function.inside)
(method_declaration) @function.around
(method_declaration body: (block) @function.inside)
(func_literal) @function.around
(func_literal body: (block) @function.inside)
(type_declaration) @class.around
(type_spec type: (struct_type (field_declaration_list) @class.inside))
(type_spec type: (interface_type) @class.inside)
(parameter_list (_) @parameter.inside @parameter.around)
(argument_list (_) @parameter.inside @parameter.around)
(comment) @comment.inside
(comment) @comment.around
