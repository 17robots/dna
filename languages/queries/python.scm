; DNA baseline highlighting; deliberately uses no host query predicates.
(comment) @comment
(string) @string
(integer) @constant
(float) @constant
(true) @constant
(false) @constant
(none) @constant
["and" "as" "assert" "async" "await" "break" "case" "class" "continue" "def" "del" "elif" "else" "except" "finally" "for" "from" "global" "if" "import" "in" "is" "lambda" "match" "nonlocal" "not" "or" "pass" "raise" "return" "try" "type" "while" "with" "yield"] @keyword
(function_definition name: (identifier) @function)
(class_definition name: (identifier) @type)
