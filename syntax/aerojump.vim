if exists("b:current_syntax")
  finish
endif

highlight SearchResult ctermbg=Green guibg=Green ctermfg=White guifg=White

highlight SearchHighlight ctermbg=Red guibg=Red ctermfg=White guifg=White

let b:current_syntax = "aerojump"
