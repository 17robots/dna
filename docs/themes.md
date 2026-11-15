# Themes

## Themes

Built-in themes: `charcoal` (default), `light`, `catppuccin-mocha`,
`catppuccin-latte`, `gruvbox-dark`, `gruvbox-light`, `nord`, `dracula`,
`tokyo-night`, `one-dark`, `solarized-dark`, `solarized-light`, `rose-pine`,
`rose-pine-moon`, `rose-pine-dawn`, `github-dark`, `github-light`, `ayu-dark`,
`ayu-mirage`, `ayu-light`, `monokai`, `kanagawa` and `everforest`. `:theme nord` switches immediately (the palette
suggests names as you type), `:themes` opens a searchable list, and `theme = "nord"` in `config.toml` keeps the choice. Each
built-in sets the editor, syntax, diagnostic and terminal ANSI colours, following
the upstream palette. `catppuccin-latte`, `gruvbox-light`, `solarized-light`,
`rose-pine-dawn`, `github-light` and `ayu-light` are light themes.

## Creating themes

Copy [themes/charcoal.toml](../themes/charcoal.toml) or
[themes/light.toml](../themes/light.toml), then edit the colours. Example:

```toml
base = "charcoal"
background = "#181818"
selection = "#354150"
syntax_keyword = "#AE9CBE"
terminal_red = "#B45F5F"
```

`base` names any built-in theme and supplies the colours (and italics) the file
does not set, so `base = "nord"` followed by one `background` line changes only
the background. Available UI roles are `background`,
`surface`, `border`, `line`, `text`, `muted`, `selection`, and `cursor`. Syntax roles
are `syntax_comment`, `syntax_string`, `syntax_keyword`, `syntax_function`,
`syntax_type`, and `syntax_constant`. ANSI roles are `terminal_black`, `terminal_red`,
`terminal_green`, `terminal_yellow`, `terminal_blue`, `terminal_magenta`,
`terminal_cyan`, `terminal_white`, and their `terminal_bright_*` variants.
Colours must be quoted six-digit `#RRGGBB` values; unknown or duplicate keys fail
validation. Full-line comments are supported.

`italic = "comment keyword"` lists the syntax roles drawn in italics (any of
`comment`, `string`, `keyword`, `function`, `type`, `constant`; default
`comment`, `""` for none). The terminal frontend draws them with the
terminal's italics; windows render with one font face and keep them upright.

Use `:theme /path/to/my-theme.toml` to apply or reload it without restarting.
`:theme` with no argument displays the selected built-in name or custom file path.
`:theme charcoal`, `:theme nord` and the other names switch back to a built-in. Invalid files
leave the current theme intact. To persist the choice, put
`theme = "~/.config/dna/themes/my-theme.toml"` in `config.toml`, then run
`:config-reload`. These shared roles colour the editor, popups, syntax, and
terminal; a theme change does not require reparsing your files.
