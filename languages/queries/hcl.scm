; HCL and Terraform highlights for DNA's capture names.
(comment) @comment
(string_lit) @string
(quoted_template) @string
(heredoc_template) @string
(heredoc_identifier) @string
(template_literal) @string
(numeric_lit) @number
(bool_lit) @constant
(null_lit) @constant
(block (identifier) @type)
(attribute (identifier) @function)
(function_call (identifier) @function)
["if" "else" "endif" "for" "endfor" "in"] @keyword
