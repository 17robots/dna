; DNA baseline highlighting; deliberately uses no host query predicates.
(comment) @comment
(html_comment) @comment
(string) @string
(template_string) @string
(number) @constant
(true) @constant
(false) @constant
(null) @constant
(type_identifier) @type
(predefined_type) @type
["abstract" "as" "assert" "async" "await" "break" "case" "catch" "class" "const" "continue" "declare" "default" "delete" "do" "else" "enum" "export" "extends" "finally" "for" "from" "function" "global" "if" "implements" "import" "in" "infer" "interface" "is" "keyof" "let" "namespace" "new" "override" "private" "protected" "public" "readonly" "return" "static" "switch" "throw" "try" "type" "using" "var" "void" "while" "with" "yield"] @keyword
(function_declaration name: (identifier) @function)
(call_expression function: (identifier) @function)
