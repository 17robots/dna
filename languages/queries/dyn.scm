; bool
(bool_) @constant.builtin.boolean

; char
(char_) @string

; comment
(comment) @comment

; constant
(const_variable (variable (identifier) @constant))
(enum_member (identifier) @constant)
(enum_shorthand (identifier) @constant)
(target_condition (identifier) @variable.other.member (identifier) @constant)
(null_) @constant.builtin

; error
; Incomplete syntax is reported by diagnostics; do not recolor whole error subtrees.

; function
(fn name: (identifier) @function)
(extern_fn name: (identifier) @function)
[ "#alignof" "#assert" "#bitcast" "#cast" "#ceil" "#floor" "#fma" "#init" "#load" "#max" "#min" "#offsetof" "#panic" "#reverse" "#round" "#sizeof" "#slice" "#sqrt" "#step" "#syscall" "#take" "#trunc" "#typeof" "#wrapping" ] @function.builtin
(call (primary (identifier) @function))
(call (primary (field_access (identifier) @function)))
(call (primary (generic_instantiation (identifier) @function)))
(call (primary (generic_instantiation (field_access (identifier) @function))))

; keyword
[ "const" "defer" "distinct" "enum" "errdefer" "extern" "fn" "nocopy" "packed" "pub" "struct" "type" "use" ] @keyword

[ "case" "catch" "else" "if" ] @keyword.control.conditional
[ "#link" "#target" ] @keyword.directive
[ (break_) (continue_) ] @keyword.control
[ "for" "in" ] @keyword.control.repeat
[ "fail" "return" "try" ] @keyword.control.return

; label
(break_ label: (identifier) @label)
(continue_ label: (identifier) @label)
(for_ label: (identifier) @label)

(primitive) @type.builtin
(type_parameter (identifier) @type)

; operator
[
  "=" "+=" "-=" "*=" "/=" "%=" "&=" "|=" ">>=" "<<=" "^="
  "+" "-" "*" "/" "%"
  "==" "!=" "<" ">" "<=" ">="
  "&&" "||"
  "!" "~"
  "&" "|" "^"
  "<<" ">>"
  ".." "..=" "=>" ".*"
] @operator
(variadic) @operator

; punctuation
[ "(" ")" "[" "]" "{" "}" ] @punctuation.bracket
[ "," "." ":" ] @punctuation.delimiter

; number
(number_) @constant.numeric

; string
(string_) @string
(escape_sequence) @string.escape
(import (string_) @string)
(import alias: (identifier) @namespace)

; type
(enum (identifier) @type)
(struct (identifier) @type)
(field_type (identifier) @type)
(type_alias (identifier) @type)
(struct_literal (identifier) @type)
(struct_literal instance: (generic_instantiation (identifier) @type))
(struct_literal instance: (generic_instantiation (field_access (identifier) @type)))

; variable
(declaration (variable (identifier) @variable))
(block (variable (identifier) @variable))
(catch_ binding: (identifier) @variable)
(for_condition (identifier) @variable)
(for_condition index: (identifier) @variable)
"_" @variable.builtin
(field_access (identifier) @variable.other.member)
(struct_literal_member (identifier) @variable.other.member)
(struct_member (identifier) @variable.other.member)
(fn_param (identifier) @variable.parameter)
(fn_type_parameter name: (identifier) @variable.parameter)
(variadic_param (identifier) @variable.parameter)
(type_pattern (identifier) @variable)
