# ============================================================================
# FILE: aerojump.py
# AUTHOR: Philip Karlsson <philipkarlsson at me.com>
# License: MIT license
# ============================================================================

import neovim
import os
import re

# Add support for different kind of _modes_

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

# Utility classes
#====================
class AerojumpLine(object):
    """ Class for a line in a aerojump buffer """
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
class Aerojump(object):
    def __init__(self, nvim):
        self.nvim = nvim
        self.logstr = []
        self.logstr.append('== Aerojump debug ==')
        # Will only be fetched when its needed
        self.tabstop = None

    def log(self, s):
        self.logstr.append(str(s))

    def open_aerojump_buf(self):
        self.nvim.command('split Aerojump')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=aerojump')
        # Fix filetype in order to keep old syntax
        self.nvim.command('set filetype='+self.ft+'.aerojump')
        self.aerojump_buf_num = self.nvim.current.buffer.number

    def open_aerojump_filter_buf(self):
        self.nvim.command('e AerojumpFilter')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=AerojumpFilter')
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
            ret.append(AerojumpLine(line, i+1))
        return ret

    def create_cursor_highlight(self):
        ret = []
        l = self.filtered_lines[self.line_filt_index]
        matches = l.matches[self.line_match_index]
        for m in matches:
            ret.append(('SearchHighlight', l.num-1, m-1, m))
        return ret

    def create_matches_highlights(self):
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

    def best_match_index_for(self, line):
        ret = 0
        for i in range(0, len(line.matches)):
            if line.scores[i] > line.scores[ret]:
                ret = i
        return ret

    def best_match_for(self, lines):
        line = lines[0]
        s_index = self.best_match_index_for(line)
        score = line.scores[s_index]

        for l in lines:
            hyp_s_index = self.best_match_index_for(l)
            # Larger score
            if ((l.scores[hyp_s_index] > score) or
                # Same score
                ((l.scores[hyp_s_index] == score) and
                # But closer to the current cursor
                (abs(self.current_pos[0] - l.num) < abs(self.current_pos[0]-line.num)))):
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

    def update_highlights(self):
        hl = self.create_matches_highlights()
        if self.has_filter:
            cursor_hl = self.create_cursor_highlight()
            for i in cursor_hl: hl.append(i)
        self.buf_ref.update_highlights(self.hl_source, hl, clear=True)

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
                # lines.append('') # Spaces could be used in a 'focus' mode
                lines.append(l.raw) # Standard VIMish mode
        self.buf_ref[:] = lines[:]
        if self.has_filter:
            cursor_pos = self.update_cursor()
            # TODO Change highlight for the current selection
            self.main_win.cursor = cursor_pos
        self.update_highlights()

    def draw(self):
        """ Draw function of the plugin """
        if self.filter_string == '':
            self.draw_unfiltered()
        else:
            self.draw_filtered()

    def create_keymap(self):
        self.nvim.command("inoremap <buffer> <C-h> <ESC>:AerojumpSelPrev<CR>")
        self.nvim.command("inoremap <buffer> <Left> <ESC>:AerojumpSelPrev<CR>")
        self.nvim.command("inoremap <buffer> <C-j> <ESC>:AerojumpDown<CR>")
        self.nvim.command("inoremap <buffer> <Down> <ESC>:AerojumpDown<CR>")
        self.nvim.command("inoremap <buffer> <C-k> <ESC>:AerojumpUp<CR>")
        self.nvim.command("inoremap <buffer> <Up> <ESC>:AerojumpUp<CR>")
        self.nvim.command("inoremap <buffer> <C-l> <ESC>:AerojumpSelNext<CR>")
        self.nvim.command("inoremap <buffer> <Right> <ESC>:AerojumpSelNext<CR>")
        self.nvim.command("inoremap <buffer> <C-q> <ESC>:AerojumpExit<CR>")
        self.nvim.command("inoremap <buffer> <ESC> <ESC>:AerojumpSelect<CR>")
        self.nvim.command("inoremap <buffer> <CR> <ESC>:AerojumpSelect<CR>")
        self.nvim.command("inoremap <buffer> aj <ESC>:AerojumpSelect<CR>")
        self.nvim.command("inoremap <buffer> <C-Space> <ESC>:AerojumpSelect<CR>")

    @neovim.autocmd("TextChangedI", pattern='AerojumpFilter', sync=True)
    def insert_changed(self):
        """ Process filter input """
        self.filter_string = self.nvim.current.line
        if self.filter_string != '':
            self.apply_filter(self.filter_string)
        self.draw()

    @neovim.command("Aerojump", range='', nargs='*', sync=True)
    def Aerojump(self, args, range):
        self.has_filter = False
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
        self.open_aerojump_filter_buf()

        # Spawn the aerojump buffer
        self.open_aerojump_buf()

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

    # Aerojump Commands
    #====================
    @neovim.command("AerojumpShowLog", range='', nargs='*', sync=True)
    def AerojumpShowLog(self, args, range):
        self.nvim.command('e Aerojump_log')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=aerojump_log')
        self.nvim.current.buffer.append(self.logstr)
        #self.nvim.current.buffer.append('== Lines Log ==')
        #for i in self.lines:
            # Add log for each line
        #    self.nvim.current.buffer.append(i.logstr)

    @neovim.command("AerojumpUp", range='', nargs='*', sync=True)
    def AerojumpUp(self, args, range):
        self.line_filt_index -= 1
        if self.line_filt_index < 0:
            self.line_filt_index = 0

        self.line_match_index = 0
        if self.has_filter > 0:
            self.main_win.cursor = self.get_current_cursor()
            self.update_highlights()

        self.nvim.command('startinsert')
        self.nvim.command('normal! $')

    @neovim.command("AerojumpDown", range='', nargs='*', sync=True)
    def AerojumpDown(self, args, range):
        self.line_filt_index += 1
        if self.line_filt_index >= len(self.filtered_lines):
            self.line_filt_index = len(self.filtered_lines) - 1

        self.line_match_index = 0
        if self.has_filter:
            self.main_win.cursor = self.get_current_cursor()
            self.update_highlights()

        self.nvim.command('startinsert')
        self.nvim.command('normal! $')

    @neovim.command("AerojumpSelNext", range='', nargs='*', sync=True)
    def AerojumpSelNext(self, args, range):
        self.line_match_index += 1
        if self.has_filter and self.line_match_index >= len(self.filtered_lines[self.line_filt_index].matches):
            self.AerojumpDown('', '')
        else:
            self.nvim.command('startinsert')
            self.nvim.command('normal! $')
        if self.has_filter > 0:
            self.main_win.cursor = self.get_current_cursor()
            self.update_highlights()

    @neovim.command("AerojumpSelPrev", range='', nargs='*', sync=True)
    def AerojumpSelPrev(self, args, range):
        self.line_match_index -= 1
        if self.line_match_index < 0:
            self.AerojumpUp('', '')
            self.line_match_index = len(self.filtered_lines[self.line_filt_index].matches) - 1
        else:
            self.nvim.command('startinsert')
            self.nvim.command('normal! $')
        if self.has_filter > 0:
            self.main_win.cursor = self.get_current_cursor()
            self.update_highlights()

    @neovim.command("AerojumpSelect", range='', nargs='*', sync=True)
    def AerojumpSelect(self, args, range):
        # TODO Add to regular vim search for further highlights
        # being able to step to next etc
        # i.e. select current word
        if self.has_filter:
            pos = self.get_current_cursor()
        else:
            pos = self.current_pos
        self.AerojumpExit('', '')
        self.nvim.current.window.cursor = pos

    @neovim.command("AerojumpExit", range='', nargs='*', sync=True)
    def AerojumpExit(self, args, range):
        self.log('AerojumpExit')
        self.nvim.command('stopinsert')
        self.nvim.current.buffer = self.og_buf
        self.nvim.command('bd %s' % self.aerojump_buf_num)
        self.nvim.command('bd %s' % self.filt_buf_num)
        # Restore original position
        self.nvim.current.window.cursor = self.top_pos
        self.nvim.command('normal! zt')
        diff = self.og_pos[0] - self.top_pos[0]
        self.nvim.command('normal! %dj' % (diff))

