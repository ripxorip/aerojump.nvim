# ============================================================================
# FILE: yaj.py
# AUTHOR: Philip Karlsson <philipkarlsson at me.com>
# License: MIT license
# ============================================================================

import neovim
import os
import re

class filter(object):
    """ Bolt inspired filter """
    def __init__(self):
        pass

    def __search(self, input, pattern, output):
        for entry in input[:]:
            res = re.search(pattern, entry, re.IGNORECASE)
            if res is not None:
                output.append(entry)
                input.remove(entry)

    def filter(self, input, pattern, output):
        # Setup patterns for the search
        beginningString = '^' + pattern + '.*'
        wholeString = '.*' + pattern + '.*'
        fuzzy = '.*'
        for c in pattern:
            fuzzy += c + '.*'
        # Perform the search
        c_currentFiles = []
        c_currentFiles[:] = input[:]
        output[:] = []
        self.__search(c_currentFiles, beginningString, output)
        self.__search(c_currentFiles, wholeString, output)
        self.__search(c_currentFiles, fuzzy, output)

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
        self.filter = filter()

    def log(self, s):
        self.logstr.append(str(s))

    def open_yaj_buf(self):
        self.nvim.command('split Yaj')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=yaj')

    def open_yaj_filter_buf(self):
        self.nvim.command('e YajFilter')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=YajFilter')

    def apply_filter(self, new_filter):
        """ Returns true/false depending on matches """
        filteredBuffer = []
        self.filter.filter(self.ogBuf, new_filter, filteredBuffer)
        return filteredBuffer

    @neovim.autocmd("TextChangedI", pattern='YajFilter', sync=True)
    def insert_changed(self):
        """ Process filter input """
        filteredBuffer = self.apply_filter(self.nvim.current.line)
        # Update the filter UI
        # self.nvim.current.line = self.nvim.current.line
        self.buf_ref[:] = filteredBuffer[:]

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

        # Spawn the filter buffer
        self.open_yaj_filter_buf()

        # Spawn the yaj buffer
        self.open_yaj_buf()

        new_buf = self.nvim.current.buffer
        # Paste the lines of the old buffer to the new
        new_buf[:] = buf[:]

        # Remember original buffer contents
        self.ogBuf = []
        self.ogBuf[:] = new_buf[:]

        # Reference to the text buffer
        self.buf_ref = new_buf
        # FIXME fetch more info (line numbers etc.)

        # Update position
        new_window = self.nvim.current.window
        new_window.cursor = top_pos
        self.nvim.command('normal! zt')

        diff = current_pos[0] - top_pos[0]
        self.nvim.command('normal! %dj' % (diff))

        # Go back to the input buffer window
        self.nvim.command('wincmd j')
        self.nvim.current.window.height = 1
        self.nvim.command("startinsert!")

        # Reset the filter string
        self.filtStr = ''

    @neovim.command("YayShowLog", range='', nargs='*', sync=True)
    def YajShowLog(self, args, range):
        self.nvim.command('e Yaj_log')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=yaj_log')
        self.nvim.current.buffer.append(self.logstr)

