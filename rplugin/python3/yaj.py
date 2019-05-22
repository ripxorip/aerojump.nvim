# ============================================================================
# FILE: yaj.py
# AUTHOR: Philip Karlsson <philipkarlsson at me.com>
# License: MIT license
# ============================================================================

import neovim
import os

def python_input(nvim, message = 'input'):
    nvim.command('call inputsave()')
    nvim.command("let user_input = input('" + message + ": ')")
    nvim.command('call inputrestore()')
    return nvim.eval('user_input')

@neovim.plugin
class Yaj(object):
    def __init__(self, nvim):
        self.nvim = nvim
        self.logstr = []
        self.logstr.append('== Yaj debug ==')

    def log(self, s):
        self.logstr.append(str(s))

    def open_yaj_buf(self):
        self.nvim.command('e Yaj')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=yaj')

    @neovim.command("Yaj", range='', nargs='*', sync=True)
    def yaj(self, args, range):
        buf = self.nvim.current.buffer
        window = self.nvim.current.window

        # Height could be used to optimize performance?
        window_height = window.height

        # Sample positions
        current_pos = window.cursor
        self.nvim.command('normal! H')
        top_pos = window.cursor
        self.nvim.command('normal! L')
        bottom_pos = window.cursor

        # Spawn the yaj buffer
        self.open_yaj_buf()

        new_buf = self.nvim.current.buffer
        # Paste the lines of the old buffer to the new
        new_buf[:] = buf[:]

        # Update position
        new_window = self.nvim.current.window
        new_window.cursor = top_pos
        self.nvim.command('normal! zt')

        diff = current_pos[0] - top_pos[0]
        self.log(diff)
        self.nvim.command('normal! %dj' % (diff))

        # Spawn the filter bar (Use the filter from bolt)
        # TODO: Cont here..

    @neovim.command("YayShowLog", range='', nargs='*', sync=True)
    def YajShowLog(self, args, range):
        self.nvim.command('e Yaj_log')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=yaj_log')
        self.nvim.current.buffer.append(self.logstr)

