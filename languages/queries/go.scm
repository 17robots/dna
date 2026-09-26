; DNA baseline highlighting; deliberately uses no host query predicates.
(comment) @comment
(raw_string_literal) @string
(interpreted_string_literal) @string
(rune_literal) @string
(float_literal) @constant
(int_literal) @constant
(imaginary_literal) @constant
(true) @constant
(false) @constant
(type_identifier) @type
["break" "case" "chan" "const" "continue" "default" "defer" "else" "fallthrough" "for" "func" "go" "goto" "if" "import" "interface" "map" "package" "range" "return" "select" "struct" "switch" "type" "var"] @keyword
(function_declaration name: (identifier) @function)
