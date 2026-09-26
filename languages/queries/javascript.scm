; DNA baseline highlighting; deliberately uses no host query predicates.
(comment) @comment
(html_comment) @comment
(string) @string
(template_string) @string
(number) @constant
(true) @constant
(false) @constant
(null) @constant
["as" "async" "await" "break" "case" "catch" "class" "const" "continue" "default" "delete" "do" "else" "export" "extends" "finally" "for" "from" "function" "if" "import" "in" "let" "new" "return" "static" "switch" "throw" "try" "using" "var" "void" "while" "with" "yield"] @keyword
(function_declaration name: (identifier) @function)
(call_expression function: (identifier) @function)
