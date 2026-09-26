; DNA baseline highlighting; deliberately uses no host query predicates.
(comment) @comment
(string_literal) @string
(raw_string_literal) @string
(char_literal) @string
(system_lib_string) @string
(number_literal) @constant
(true) @constant
(false) @constant
(null) @constant
(primitive_type) @type
(type_identifier) @type
["and" "break" "case" "catch" "class" "const" "continue" "default" "delete" "do" "else" "enum" "export" "extern" "for" "goto" "if" "import" "namespace" "new" "not" "or" "override" "private" "protected" "public" "return" "sizeof" "static" "struct" "switch" "template" "throw" "try" "typedef" "typename" "union" "using" "virtual" "volatile" "while"] @keyword
(function_declarator declarator: (identifier) @function)
