# ============================================================================
# FILE: yaj.py
# AUTHOR: Philip Karlsson <philipkarlsson at me.com>
# License: MIT license
# ============================================================================

import neovim
import os
import re

# Utility functions
#====================
def python_input(nvim, message = 'input'):
    nvim.command('call inputsave()')
    nvim.command("let user_input = input('" + message + ": ')")
    nvim.command('call inputrestore()')
    return nvim.eval('user_input')

# Utility classes
#====================
class Filter(object):
    """ Bolt inspired filter  (kept for reference)
        filter is moved to each line instead"""
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

class YajLine(object):
    """ Class for a line in a yaj buffer """
    def __init__(self, line, num):
        # Raw text
        self.raw = line
        # Line number
        self.num = num
        # Matches in this line
        self.matches = []

    def filter(self, pattern):
        # Create the filter patterns
        # TODO: Cont. here write my _own_ matcher:
        # 1. Find index of all filter characters
        # 2. Match from right to left
        # 3. Filter out words from 'fuzzy partials'
        # 4. Create score for the line (partial and full)

        wholeString = pattern
        fuzzy = '.*'
        for c in pattern:
            fuzzy += '(' + c + ')' + '.*'
        patterns = {}
        patterns['whole'] = wholeString
        patterns['fuzzy'] = fuzzy

        # Perform the search
        self.res = {}
        for pat in patterns:
            # The iter works
            self.res[pat] = re.finditer(patterns[pat], self.raw, re.IGNORECASE)

        # Reset the matches
        self.matches = []
        # Classify/quantify matches
        m = self.res['whole']
        if m != None:
            for i in m:
                pass
                self.matches.append(i.span())

        m = self.res['fuzzy']
        if m != None:
            for i in m:
                for j in range(1, i.lastindex):
                    self.matches.append(i.span(j))

        # Filter out duplicates
        filtered_matches = []


@neovim.plugin
class Yaj(object):
    def __init__(self, nvim):
        self.nvim = nvim
        self.logstr = []
        self.logstr.append('== Yaj debug ==')
        self.filter = Filter()

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

    def set_original_cursor_position(self):
        old_win = self.nvim.current.window
        self.nvim.current.window = self.main_win
        self.nvim.current.window.cursor = self.top_pos
        self.nvim.command('normal! zt')

        diff = self.current_pos[0] - self.top_pos[0]
        self.nvim.command('normal! %dj' % (diff))
        self.nvim.current.window = old_win

    def apply_filter(self, filter_string):
        for l in self.lines:
            l.filter(filter_string)
            if l.matches != []:
                self.log(l.raw)
            for m in l.matches:
                self.log(str(m))

    def get_lines(self, lines):
        ret = []
        for i, line in enumerate(lines):
            ret.append(YajLine(line, i+1))
        return ret

    def draw_unfiltered(self):
        lines = []
        for l in self.lines:
            lines.append(l.raw)
        self.buf_ref[:] = lines[:]
        # Reset original cursor position
        self.set_original_cursor_position()

    def draw(self):
        """ Draw function of the plugin """
        if self.filter_string == '':
            self.draw_unfiltered()
        else:
            # FIXME make real implementation of the filtered words,
            # highlights etc..
            self.buf_ref[:] = ['ok', 'dok']

    @neovim.autocmd("TextChangedI", pattern='YajFilter', sync=True)
    def insert_changed(self):
        """ Process filter input """
        self.filter_string = self.nvim.current.line
        self.apply_filter(self.filter_string)
        self.draw()

    @neovim.command("Yaj", range='', nargs='*', sync=True)
    def yaj(self, args, range):
        buf = self.nvim.current.buffer
        window = self.nvim.current.window

        # Height could be used to optimize performance?
        window_height = window.height

        # Sample positions
        self.current_pos = window.cursor
        self.nvim.command('normal! H')
        self.top_pos = window.cursor
        self.nvim.command('normal! L')

        # Spawn the filter buffer
        self.open_yaj_filter_buf()

        # Spawn the yaj buffer
        self.open_yaj_buf()

        new_buf = self.nvim.current.buffer
        # Paste the lines of the old buffer to the new
        new_buf[:] = buf[:]

        # Create lines
        self.lines = self.get_lines(new_buf)

        # Reference to the text buffer
        self.buf_ref = new_buf

        # Update position
        self.main_win = self.nvim.current.window

        # Go back to the input buffer window
        self.nvim.command('wincmd j')
        self.nvim.current.window.height = 1
        self.nvim.command("startinsert!")

        # Reset the filter string
        self.filter_string = ''
        self.draw()
        self.set_original_cursor_position()

    @neovim.command("YayShowLog", range='', nargs='*', sync=True)
    def YajShowLog(self, args, range):
        self.nvim.command('e Yaj_log')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=yaj_log')
        self.nvim.current.buffer.append(self.logstr)

