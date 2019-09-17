# aerojump.nvim


![Aerojump logo](img/logo.svg?sanitize=true)

Aerojump is a fuzzy-match searcher/jumper for Neovim. Its goal is to enable fast
navigation through searching using the keyboard. It features several modes
which can be used depending on your needs. By using an intelligent scoring
system it will move the cursor to the best match based on your input.

## Demo

### Space mode
![Example Highlight](https://imgur.com/eUYLI3Q.gif)

Quickly move the cursor the line you want to go by typing some letters
present in the line. All other lines are filtered away as you continue typing.

### Bolt mode
![Example Highlight](https://imgur.com/evbd5Ad.gif)

Perform a search using fuzzy-matching, results are graded through a scoring system
presenting the most relevant hits first.

### Boring mode
![Example Highlight](https://imgur.com/prtHSML.gif)

Space mode but unmatched lines are left intact.

## Installation

**Note:** aerojump.nvim requires Neovim(latest is recommended) with Python3 enabled.
See [requirements](#requirements) if you aren't sure whether you have this.

```vim
" Install plugin using (in this example using VimPlug)

call plug#begin()

Plug 'philip-karlsson/aerojump.nvim', { 'do': ':UpdateRemotePlugins' }

call plug#end()

" Create mappings (with leader)
nmap <Leader>as <Plug>(AerojumpSpace)
nmap <Leader>ab <Plug>(AerojumpBolt)
nmap <Leader>aa <Plug>(AerojumpFromCursorBolt)
nmap <Leader>ad <Plug>(AerojumpDefault) " Boring mode
....

" Or create mappings (without leader)
nmap <space> <Plug>(AerojumpSpace)
```

## Usage

Invoke aerojump in the desired mode. Start typing some characters that matches
where you will go and finish the query by pressing either `enter` (to go there)
or `escape` to return to where you were in the buffer before.

### Keybindings
| Command               | Action                                                                                |
| ---                   | ---                                                                                   |
| `enter`               | Move cursor to the selected result
| `esc`                 | Move cursor the the selected result
| `aj`                  | Move cursor the the selected result
| `Space`               | Move cursor the the selected result
| `C-q`                 | Exit aerojump (cursor moves back to original position)
| `Ctrl-j/k`            | Navigate line wise (up/down)
| `Ctrl-h/l`            | Navigate match wise (next/previous)
| `C-space`             | Move cursor to the selected result

## Self-Promotion
Like aerojump.nvim? Make sure to follow the repository and why not leave a star.

## Contributors
- Philip Karlsson Gisslow

## License
MIT License

Copyright (c) 2019 Philip Karlsson Gisslow

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
