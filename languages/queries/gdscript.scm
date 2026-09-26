; GDScript highlights for DNA's capture names (comment, string, keyword,
; function, type, constant, number).
(comment) @comment
(string) @string
(string_name) @string
(node_path) @string
(get_node) @string
(escape_sequence) @string
(integer) @number
(float) @number
[(true) (false) (null)] @constant
(type) @type
(class_name_statement (name) @type)
(extends_statement (type) @type)
(enum_definition name: (name) @type)
(function_definition name: (name) @function)
(constructor_definition) @function
(call (identifier) @function)
(attribute_call (identifier) @function)
(signal_statement (name) @function)
(annotation) @keyword
(static_keyword) @keyword
(remote_keyword) @keyword
(const_statement name: (name) @constant)
[
  "and" "as" "await" "break" "class" "const" "continue" "elif" "else" "enum"
  "export" "extends" "for" "func" "get" "if" "in" "is" "match" "not"
  "onready" "or" "pass" "return" "set" "setget" "signal" "var" "when" "while"
] @keyword
