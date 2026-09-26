; DNA baseline highlighting; deliberately uses no host query predicates.
(comment) @comment
(string_literal) @string
(char_literal) @string
(system_lib_string) @string
(number_literal) @constant
(true) @constant
(false) @constant
(null) @constant
(primitive_type) @type
(type_identifier) @type
["break" "case" "const" "continue" "default" "do" "else" "enum" "extern" "for" "goto" "if" "return" "sizeof" "static" "struct" "switch" "typedef" "union" "volatile" "while"] @keyword
(function_declarator declarator: (identifier) @function)
