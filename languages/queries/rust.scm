; DNA baseline highlighting; deliberately uses no host query predicates.
(line_comment) @comment
(block_comment) @comment
(string_literal) @string
(raw_string_literal) @string
(char_literal) @string
(integer_literal) @constant
(float_literal) @constant
(boolean_literal) @constant
(primitive_type) @type
(type_identifier) @type
["as" "async" "await" "break" "const" "continue" "default" "dyn" "else" "enum" "extern" "fn" "for" "if" "impl" "in" "let" "loop" "match" "mod" "move" "pub" "ref" "return" "static" "struct" "trait" "try" "type" "union" "unsafe" "use" "where" "while" "yield"] @keyword
(function_item name: (identifier) @function)
