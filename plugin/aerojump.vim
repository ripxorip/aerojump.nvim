" Author: Philip <philipkarlsson@me.com>
" Description: Main entry point for the plugin: sets up prefs and autocommands
"   Preferences can be set in vimrc files and so on to configure aerojump

nnoremap <silent> <Plug>(AerojumpDefault) :Aerojump default<Return>

nnoremap <silent> <Plug>(AerojumpResumeNext) :AerojumpResumeNext<Return>
nnoremap <silent> <Plug>(AerojumpResumePrev) :AerojumpResumePrev<Return>
