" Author: Philip <philipkarlsson@me.com>
" Description: Main entry point for the plugin: sets up prefs and autocommands
"   Preferences can be set in vimrc files and so on to configure aerojump

nnoremap <silent> <Plug>(AerojumpDefault) :Aerojump kbd default<Return>
nnoremap <silent> <Plug>(AerojumpSpace) :Aerojump kbd space<Return>
nnoremap <silent> <Plug>(AerojumpBolt) :Aerojump kbd bolt<Return>
nnoremap <silent> <Plug>(AerojumpMilk) :Aerojump kbd milk<Return>

nnoremap <silent> <Plug>(AerojumpFromCursorBolt) :Aerojump cursor bolt <cword> <Return>

nnoremap <silent> <Plug>(AerojumpShowLog) :AerojumpShowLog<Return>
nnoremap <silent> <Plug>(AerojumpResumeNext) :AerojumpResumeNext<Return>
nnoremap <silent> <Plug>(AerojumpResumePrev) :AerojumpResumePrev<Return>
