# ============================================================================
# FILE: yaj.py
# AUTHOR: Philip Karlsson <philipkarlsson at me.com>
# License: MIT license
# ============================================================================

import neovim
import os
import re

# This project will be forked to create 'aerojumper'
# instead. Aero because of space when no matches
# Add support for different kind of _modes_ too..

# Cool idea:
# Only delete with space if its in the visible range,
# otherwise use 'commented' highlights for results
# that way it can be a good searcher too. Also rethink
# if I want to match in another way when its not visible.

# Also prioritize close to cursor if tie between scores

# Utility functions
#====================
def get_output_of_vim_cmd(nvim, cmd):
    nvim.command('redir @a')
    nvim.command(cmd)
    nvim.command('redir END')
    return nvim.eval('@a').strip('\n')

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

    def __score_matches(self, matches, pat_len):
        sorted_matches = []
        self.scores = []
        for m in matches:
            i = 0
            score = 1
            while i < len(m):
                num = m[i]
                c_match = [m[i]]
                while i < len(m) - 1 and m[i+1] - m[i] == 1:
                    c_match.append(m[i+1])
                    score += 1
                    i += 1
                i += 1
                if c_match not in sorted_matches:
                    sorted_matches.append(c_match)
            self.scores.append(score/pat_len)
        return sorted_matches

    def __match_from(self, matches, pattern, pat_index, word_index):
        for i in range(word_index, len(self.raw)):
            if self.raw_lower[i] == pattern[pat_index]:
                matches.append(i+1)
                next_pat_index = pat_index + 1
                next_word_index = i + 1
                # Final match in the pattern
                if next_pat_index == len(pattern):
                    return True
                # More characters to process
                elif next_word_index < len(self.raw_lower):
                    # Recursion :)
                    return self.__match_from(matches, pattern, next_pat_index, next_word_index)
                # No more characters left to process but pattern is complete
                else:
                    return False
        return False

    def filter(self, pattern):
        # Reset the matches
        self.matches = []

        for i in range(0, len(self.raw_lower)):
            # Reset the proposed matches
            proposed_matches = []
            # Start with last pattern c and last char of raw
            if self.raw_lower[i] == pattern[0]:
                if self.__match_from(proposed_matches, pattern, 0, i):
                    self.matches.append(proposed_matches)

        # 1.0 equals full match, thereafter fuzzy partials
        self.__score_matches(self.matches, len(pattern))

        # Sorting example fore future reference, the parent class
        # matches[:] = sorted_matches[:]
        # matches = matches.sort(key=len, reverse=True)


@neovim.plugin
class Yaj(object):
    def __init__(self, nvim):
        self.nvim = nvim
        self.logstr = []
        self.logstr.append('== Yaj debug ==')
        # Will only be fetched when its needed
        self.tabstop = None

    def log(self, s):
        self.logstr.append(str(s))

    def open_yaj_buf(self):
        self.nvim.command('split Yaj')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=yaj')
        # Fix filetype in order to keep old syntax
        self.nvim.command('set filetype='+self.ft+'.yaj')
        self.yaj_buf_num = self.nvim.current.buffer.number

    def open_yaj_filter_buf(self):
        self.nvim.command('e YajFilter')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=YajFilter')
        self.filt_buf_num = self.nvim.current.buffer.number

    def set_original_cursor_position(self):
        old_win = self.nvim.current.window
        self.nvim.current.window = self.main_win
        self.nvim.current.window.cursor = self.top_pos
        self.nvim.command('normal! zt')

        diff = self.og_pos[0] - self.top_pos[0]
        self.nvim.command('normal! %dj' % (diff))
        self.nvim.current.window = old_win

    def apply_filter(self, filter_string):
        self.filtered_lines = []
        filt_index = 0
        for l in self.lines:
            l.filter(filter_string)
            if l.matches != []:
                l.filt_index = filt_index
                self.filtered_lines.append(l)
                filt_index += 1
                # self.log(l.raw)
            continue
            for m in l.matches:
                self.log(str(m))
        self.has_filter = len(self.filtered_lines) > 0

    def get_lines(self, lines):
        ret = []
        for i, line in enumerate(lines):
            ret.append(YajLine(line, i+1))
        return ret

    def create_highlights(self):
        ret = []
        for l in self.lines:
            for m in l.matches:
                # TODO optimize
                for i in m:
                    # TODO Fix -1 offset bug for l.num
                    # TODO Fix offset error for tabs, (may already be solved)
                    ret.append(('SearchResult', l.num-1, i-1, i))
        return ret

    def get_current_cursor(self):
        l = self.filtered_lines[self.line_filt_index]
        return (l.num, l.matches[self.line_match_index][0]-1)

    def best_score_for(self, line):
        ret = 0
        for i in range(0, len(line.matches)):
            if line.scores[i] > line.scores[ret]:
                ret = i
        return ret

    def best_match_for(self, lines):
        line = lines[0]
        s_index = self.best_score_for(line)
        score = line.scores[s_index]

        for l in lines:
            hyp_s_index = self.best_score_for(l)
            if l.scores[hyp_s_index] > score:
                score = l.scores[hyp_s_index]
                s_index = hyp_s_index
                line = l
        # Update internal indices
        self.line_filt_index = line.filt_index
        self.line_match_index = s_index
        return self.get_current_cursor()

    def update_cursor(self):
        # Get information for the currently visible lines
        visible_start = self.top_pos[0]
        visible_end = visible_start + self.window_height # Might be -1?

        # Get visible matches
        visible_matches = [l for l in self.filtered_lines if l.num >= visible_start and l.num <= visible_end]
        if visible_matches != []:
            return self.best_match_for(visible_matches)
        else:
            return self.best_match_for(self.filtered_lines)

    def _update_cursor(self):
        # Different kind of matching, different mode?
        # Saved for reference
        # Get information for the currently visible lines
        visible_start = self.top_pos[0]
        visible_end = visible_start + self.window_height # Might be -1?

        # Might also be - 1?
        current_line = self.current_pos[0]

        # Find current_line in line
        found_line = False
        num_matches = len(self.filtered_lines)
        if num_matches == 0:
            # No matches
            return

        filt_index = 0
        if self.filtered_lines[filt_index].num >= current_line:
            found_line = True
        else:
            for i in range(0, len(self.filtered_lines)-1):
                if self.filtered_lines[i].num <= current_line and self.filtered_lines[i+1].num > current_line:
                    found_line = True
                    filt_index = i
        if not found_line:
            self.log('ERROR! SHOULD HAVE FOUND A LINE BY NOW')
            return

        return (0, 0)

    def draw_unfiltered(self):
        lines = []
        for l in self.lines:
            lines.append(l.raw)
        self.buf_ref[:] = lines[:]
        self.log('Unfiltered')
        # Reset original cursor position
        self.set_original_cursor_position()
        self.buf_ref.clear_highlight(self.hl_source)

    def draw_filtered(self):
        lines = []
        for l in self.lines:
            if l.matches != []:
                lines.append(l.raw)
                for i, m in enumerate(l.matches):
                    continue
                    # Debug
                    lines.append(str(l.scores[i]))
                    lines.append(str(m))
            else:
                # Newlines or commenting text, will start with newlines
                lines.append('')
        self.buf_ref[:] = lines[:]
        hl = self.create_highlights()
        self.buf_ref.update_highlights(self.hl_source, hl, clear=True)

        if self.has_filter:
            cursor_pos = self.update_cursor()
            # TODO Change highlight for the current selection
            self.main_win.cursor = cursor_pos

    def draw(self):
        """ Draw function of the plugin """
        if self.filter_string == '':
            self.draw_unfiltered()
        else:
            self.draw_filtered()

    def create_keymap(self):
        self.nvim.command("inoremap <buffer> <C-h> <ESC>:YajSelPrev<CR>")
        self.nvim.command("inoremap <buffer> <Left> <ESC>:YajSelPrev<CR>")
        self.nvim.command("inoremap <buffer> <C-j> <ESC>:YajDown<CR>")
        self.nvim.command("inoremap <buffer> <Down> <ESC>:YajDown<CR>")
        self.nvim.command("inoremap <buffer> <C-k> <ESC>:YajUp<CR>")
        self.nvim.command("inoremap <buffer> <Up> <ESC>:YajUp<CR>")
        self.nvim.command("inoremap <buffer> <C-l> <ESC>:YajSelNext<CR>")
        self.nvim.command("inoremap <buffer> <Right> <ESC>:YajSelNext<CR>")
        self.nvim.command("inoremap <buffer> <C-q> <ESC>:YajExit<CR>")
        self.nvim.command("inoremap <buffer> <ESC> <ESC>:YajExit<CR>")
        self.nvim.command("inoremap <buffer> <CR> <ESC>:YajSelect<CR>")
        self.nvim.command("inoremap <buffer> <C-Space> <ESC>:YajSelect<CR>")

    @neovim.autocmd("TextChangedI", pattern='YajFilter', sync=True)
    def insert_changed(self):
        """ Process filter input """
        self.filter_string = self.nvim.current.line
        if self.filter_string != '':
            self.apply_filter(self.filter_string)
        self.draw()

    @neovim.command("Yaj", range='', nargs='*', sync=True)
    def yaj(self, args, range):
        self.hl_source = self.nvim.new_highlight_source()
        self.og_buf = self.nvim.current.buffer
        window = self.nvim.current.window

        # Height could be used to optimize performance?
        self.window_height = window.height

        # Sample positions
        self.current_pos = window.cursor
        self.og_pos = window.cursor
        self.nvim.command('normal! H')
        self.top_pos = window.cursor
        self.nvim.command('normal! L')

        # Sample current filetype
        resp = get_output_of_vim_cmd(self.nvim, 'set filetype?')
        self.ft = resp.split('=')[1]

        # Spawn the filter buffer
        self.open_yaj_filter_buf()

        # Spawn the yaj buffer
        self.open_yaj_buf()

        new_buf = self.nvim.current.buffer
        # Paste the lines of the old buffer to the new
        new_buf[:] = self.og_buf[:]

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

        # Create keymap
        self.create_keymap()

    # Yaj Commands
    #====================
    @neovim.command("YajShowLog", range='', nargs='*', sync=True)
    def YajShowLog(self, args, range):
        self.nvim.command('e Yaj_log')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=yaj_log')
        self.nvim.current.buffer.append(self.logstr)
        #self.nvim.current.buffer.append('== Lines Log ==')
        #for i in self.lines:
            # Add log for each line
        #    self.nvim.current.buffer.append(i.logstr)

    @neovim.command("YajUp", range='', nargs='*', sync=True)
    def YajUp(self, args, range):
        self.line_filt_index -= 1
        if self.line_filt_index < 0:
            self.line_filt_index = 0

        self.line_match_index = 0
        if self.has_filter > 0:
            self.main_win.cursor = self.get_current_cursor()

        self.nvim.command('startinsert')
        self.nvim.command('normal! $')

    @neovim.command("YajDown", range='', nargs='*', sync=True)
    def YajDown(self, args, range):
        self.line_filt_index += 1
        if self.line_filt_index >= len(self.filtered_lines):
            self.line_filt_index = len(self.filtered_lines) - 1

        self.line_match_index = 0
        if self.has_filter:
            self.main_win.cursor = self.get_current_cursor()

        self.nvim.command('startinsert')
        self.nvim.command('normal! $')

    @neovim.command("YajSelNext", range='', nargs='*', sync=True)
    def YajSelNext(self, args, range):
        self.line_match_index += 1
        if self.has_filter and self.line_match_index >= len(self.filtered_lines[self.line_filt_index].matches):
            self.YajDown('', '')
        else:
            self.nvim.command('startinsert')
            self.nvim.command('normal! $')
        if self.has_filter > 0:
            self.main_win.cursor = self.get_current_cursor()

    @neovim.command("YajSelPrev", range='', nargs='*', sync=True)
    def YajSelPrev(self, args, range):
        self.line_match_index -= 1
        if self.line_match_index < 0:
            self.YajUp('', '')
        else:
            self.nvim.command('startinsert')
            self.nvim.command('normal! $')
        if self.has_filter > 0:
            self.main_win.cursor = self.get_current_cursor()

    @neovim.command("YajSelect", range='', nargs='*', sync=True)
    def YajSelect(self, args, range):
        # TODO Add to regular vim search for further highlights
        # being able to step to next etc
        # i.e. select current word
        pos = self.get_current_cursor()
        self.YajExit('', '')
        self.nvim.current.window.cursor = pos

    @neovim.command("YajExit", range='', nargs='*', sync=True)
    def YajExit(self, args, range):
        self.log('YajExit')
        self.nvim.command('stopinsert')
        self.nvim.current.buffer = self.og_buf
        self.nvim.command('bd %s' % self.yaj_buf_num)
        self.nvim.command('bd %s' % self.filt_buf_num)
        # Restore original position
        self.nvim.current.window.cursor = self.top_pos
        self.nvim.command('normal! zt')
        diff = self.og_pos[0] - self.top_pos[0]
        self.nvim.command('normal! %dj' % (diff))

