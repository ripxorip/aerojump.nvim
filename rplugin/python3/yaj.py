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
class YajLine(object):
    """ Class for a line in a yaj buffer """
    def __init__(self, line, num):
        # Raw text
        self.raw = line
        self.raw_lower = line.lower()
        # Line number
        self.num = num
        # Matches in this line
        self.matches = []
        self.logstr = []

    def log(self, s):
        self.logstr.append(str(s))

    def __match_from(self, matches, pattern, pat_index, word_index):
        match = False

        if word_index == 0 and pattern[pat_index] == self.raw_lower[word_index] and pat_index == 0:
            matches.append(1)
            return True

        for i in reversed((range(0, word_index+1))):
            if self.raw_lower[i] == pattern[pat_index]:
                matches.append(i+1)
                match = True
                matched_index = i
                break

            # FIXME: Too simplistic, might need more _recursion_ ! Cont here.. log try 'sth'
            # Quick fick: helper function to get the 'leftmost' occurence of the character instead
            # Wont work either...
            # Can I skip it, only break if full match found when left to right??
            # SEEMS LIKE IT!
            elif pat_index + 1 < len(pattern) + 1 and self.raw_lower[i] == pattern[pat_index + 1]:
                pass

        if match:
            next_pat_index = pat_index - 1
            next_word_index = matched_index - 1
            # Final match in the pattern
            if next_pat_index < 0:
                return True
            # More characters to process
            elif next_word_index >= 0:
                # Recursion :)
                return self.__match_from(matches, pattern, next_pat_index, next_word_index)
            # No more characters left to process but pattern is complete
            else:
                return False
        else:
            return False


    def filter(self, pattern):
        # 1. Find index of all filter characters [done]
        # 2. Match from right to left [done]
        # 3. Filter out words from 'fuzzy partials'
        # 4. Create score for the line (partial and full)

        # Reset the matches
        self.matches = []

        # Reverse loop over a list
        for i in reversed((range(0, len(self.raw)))):
            # Reset the proposed matches
            proposed_matches = []
            # Start with last pattern c and last char of raw
            if self.raw_lower[i] == pattern[len(pattern)-1]:
                if self.__match_from(proposed_matches, pattern, len(pattern)-1, i):
                    self.matches.append(proposed_matches)

        for m in self.matches:
            # Reverse results
            m.reverse()
            # TODO Sort matches etc

@neovim.plugin
class Yaj(object):
    def __init__(self, nvim):
        self.nvim = nvim
        self.logstr = []
        self.logstr.append('== Yaj debug ==')

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
            ret.append(YajLine(line[::-1], i+1))
        return ret

    def draw_unfiltered(self):
        lines = []
        for l in self.lines:
            lines.append(l.raw_lower[::-1])
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
            self.buf_ref[:] = []
            for l in self.lines:
                if l.matches != []:
                    self.buf_ref.append(l.raw_lower[::-1])
                    for m in l.matches:
                        self.buf_ref.append(str(m))

    @neovim.autocmd("TextChangedI", pattern='YajFilter', sync=True)
    def insert_changed(self):
        """ Process filter input """
        self.filter_string = self.nvim.current.line
        if self.filter_string != '':
            self.apply_filter(self.filter_string[::-1])
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

        # Fetch current tabstop
        # needed in order to convert character
        # position to vim position
        self.nvim.command('redir @a')
        self.nvim.command('set tabstop?')
        self.nvim.command('redir END')
        self.tabstop = [int(s) for s in self.nvim.eval('@a').strip('\n').split('=') if s.isdigit()][0]

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
        #self.nvim.current.buffer.append('== Lines Log ==')
        #for i in self.lines:
            # Add log for each line
        #    self.nvim.current.buffer.append(i.logstr)

