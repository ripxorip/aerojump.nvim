# ============================================================================
# FILE: aerojump.py
# AUTHOR: Philip Karlsson Gisslow <philipkarlsson at me.com>
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

# Aerojump classes
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
        if pattern == '':
            # Can't filter empty pattern
            return

        for i in range(0, len(self.raw_lower)):
            # Reset the proposed matches
            proposed_matches = []
            # Start with last pattern c and last char of raw
            if self.raw_lower[i] == pattern[0]:
                if self.__match_from(proposed_matches, pattern, 0, i):
                    self.matches.append(proposed_matches)

        # 1.0 equals full match, thereafter fuzzy partials
        self.__score_matches(self.matches, len(pattern))

        # Sorting example for future reference, the parent class
        # matches[:] = sorted_matches[:]
        # matches = matches.sort(key=len, reverse=True)


class Aerojump(object):
    """ The main class of aerojump """
    def __init__(self, lines, lin_nums, cursor_pos, top_line, num_lines):
        """ Constructor for the aerojump class

        Parameters:
            lines:      array of the lines of a buffer

            lin_nums:   array of the lin_nums for
                        each line in 'line'

            cursor_pos: cursor position when plugin is
                        summoned

            top_line:   top-most line visible in the editor
                        when its summoned (used to keep positioning)

            num_lines:  number of currently visible lines

        Returns:
            an Aerojump object

        """
        self.log_str = []

        # Store intial cursor/windows potisioning
        self.og_top_line = top_line
        self.og_cursor_pos = cursor_pos
        self.num_lines = num_lines

        self.filter_string = ''
        self.lines = []
        for i in range(0, len(lines)):
            self.lines.append(AerojumpLine(lines[i], lin_nums[i]))

    def log(self, log_str):
        """ Log function for Aerojump

        Parameters:
            log_str: string to be logged

        Returns:
            n/a
        """
        self.log_str.append(str(log_str))

    def get_log(self):
        """ Fetch the current log

        Parameters:
            n/a

        Returns:
            List of string for the log
        """
        return self.log_str

    def apply_filter(self, filter_string):
        """ Filtering function

        Parameters:

            filter_string: string that will be used as filter

        Returns:
            n/a

        """
        self.filter_string = filter_string
        self.filtered_lines = self.__get_filtered_lines(filter_string, self.lines)
        self.has_filter_results = len(self.filtered_lines) > 0

        if self.has_filter_results:
            cursor_indices = self.__set_cursor_to_best_match()
            self.cursor_line_index = cursor_indices[0]
            self.cursor_match_index = cursor_indices[1]
            #FIXME split this line
            self.highlights = self.__update_highlights(self.lines, self.filtered_lines, self.cursor_line_index, self.cursor_match_index)

    def draw(self):
        """ Draw function of the plugin

        Parameters:
            n/a

        Returns:
            Dict containing (lines_to_draw, highlights, cursor_position, top_line):

                lines_to_draw:   content of the lines that shall be drawn
                highlights:      highlights that shall be painted in the editor
                cursor_position: current cursor position
                top_line:        Top-most line that shall be visisble in the editor
                                 ((-1, -1) if it shall be up the editor to position the cursor)
        """
        if self.filter_string == '':
            return self.__draw_unfiltered()
        else:
            return self.__draw_filtered()

    def get_cursor(self):
        """ Gets the current cursor position

        Parameters:
            n/a

        Returns:
            Tuple containing the current cursor position
        """
        if not self.has_filter_results:
            return (1, 1)

        l = self.filtered_lines[self.cursor_line_index]
        return (l.num, l.matches[self.cursor_match_index][0]-1)

    def __draw_filtered(self):
        """ Draw function of the plugin for filtered results

        In the future, this function shall be implemented differently depending on mode

        Parameters:
            n/a

        Returns:
            Dict containing (lines_to_draw, highlights, cursor_position, top_line)
        """
        lines = []
        for l in self.lines:
            if l.matches != []:
                lines.append(l.raw)
            else:
                # E.g. of a mode
                # lines.append('')
                lines.append(l.raw)

        return {'lines':            lines,
                'highlights':       self.highlights,
                'cursor_position':  self.get_cursor(),
                # The editor sets the position
                'top_line':         (-1, -1)}

    def __draw_unfiltered(self):
        """ Draw function of the plugin for unfiltered results

        Parameters:
            n/a

        Returns:
            Dict containing (lines_to_draw, highlights, cursor_position, top_line)
        """
        # Create lines
        lines = []
        for l in self.lines:
            lines.append(l.raw)

        return {'lines':            lines,
                'highlights':       [],
                'cursor_position':  self.og_cursor_pos,
                'top_line':         self.og_top_line}

    def __best_match_index_for(self, line):
        """ Returns the highest match for line

        Parameters:
            line: Line that will be checked

        Returns:
            Index of the best match
        """
        ret = 0
        for i in range(0, len(line.matches)):
            if line.scores[i] > line.scores[ret]:
                ret = i
        return ret

    def __best_cursor_in(self, lines):
        """ Returns the best cursor indices among the lines

        Parameters:
            lines: lines to find the best cursor for

        Returns:
            Tuple containing (line_index, match_index)
                line_index: index for the best line
                match_index: index for the best match of that line
        """
        line = lines[0]
        s_index = self.__best_match_index_for(line)
        score = line.scores[s_index]

        for l in lines:
            hyp_s_index = self.__best_match_index_for(l)
            # Larger score
            if ((l.scores[hyp_s_index] > score) or
                # Same score
                ((l.scores[hyp_s_index] == score) and
                # But closer to the original cursor position
                (abs(self.og_cursor_pos[0] - l.num) < abs(self.og_cursor_pos[0]-line.num)))):
                score = l.scores[hyp_s_index]
                s_index = hyp_s_index
                line = l
        return(line.filt_index, s_index)

    def __set_cursor_to_best_match(self):
        """ Updates the internal cursor position

        Parameters:
            n/a

        Returns:
            Tuple containing (line_index, match_index)
                line_index: index for the best line
                match_index: index for the best match of that line
        """
        # Get information for the currently visible lines
        visible_start = self.og_top_line[0]
        visible_end = visible_start + self.num_lines # Might need to add -1?

        # Get visible matches
        visible_matches = [l for l in self.filtered_lines if l.num >= visible_start and l.num <= visible_end]
        if visible_matches != []:
            ret = self.__best_cursor_in(visible_matches)
        else:
            ret = self.__best_cursor_in(self.filtered_lines)
        return ret

    def __update_highlights(self, lines, filtered_lines, cursor_line_index, cursor_match_index):
        """ Updates the internal highlights

        NOTE: This function can likely be simplified, might only need to look at filtered_lines?

        Parameters:
            lines: All lines of the buffer
            filtered_lines: Filtered lines of the buffer
            cursor_line_index: Line index for the cursor
            cursor_match_index: Match index of the line at cursor

        Returns:
            List with highlights
        """
        highlights = []
        # Match highlights
        for l in lines:
            for m in l.matches:
                # TODO optimize
                for i in m:
                    # TODO Fix -1 offset bug for l.num
                    # TODO Fix offset error for tabs, (may already be solved)
                    highlights.append(('SearchResult', l.num-1, i-1, i))
        # Cursor highlights
        l = filtered_lines[cursor_line_index]
        matches = l.matches[cursor_match_index]
        for m in matches:
            highlights.append(('SearchHighlight', l.num-1, m-1, m))
        return highlights


    def __get_filtered_lines(self, filter_string, lines):
        """ Get filtered lines

        Parameters:
            filter_string:  filter string
            lines:          lines to be filtered

        Returns:
            filtered_lines
        """
        filtered_lines = []
        filt_index = 0
        for l in lines:
            l.filter(filter_string)
            if l.matches != []:
                l.filt_index = filt_index
                filtered_lines.append(l)
                filt_index += 1
        return filtered_lines

@neovim.plugin
class AerojumpNeovim(object):
    """ Neovim interface """
    def __init__(self, nvim):
        self.nvim = nvim
        self.logstr = []
        self.logstr.append('== Aerojump debug ==')
        self.has_searched = False

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
        self.set_cursor_position(self.top_pos, self.og_pos)
        self.nvim.current.window.cursor = self.og_pos
        self.nvim.current.window = old_win

    def set_cursor_position(self, pos):
        old_win = self.nvim.current.window
        self.nvim.current.window = self.main_win
        self.nvim.current.window.cursor = pos
        self.nvim.current.window = old_win

    def set_top_pos(self, top_pos):
        old_win = self.nvim.current.window
        self.nvim.current.window = self.main_win
        self.nvim.current.window.cursor = top_pos
        self.nvim.command('normal! zt')
        self.nvim.current.window = old_win

    def apply_filter(self, filter_string):
        self.aj.apply_filter(filter_string)
        return

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

    def create_aerojumper(self, lines, cursor_pos, top_line, num_lines):
        lin_nums = []
        for i, line in enumerate(lines):
            lin_nums.append(i+1)
        return Aerojump(lines, lin_nums, cursor_pos, top_line, num_lines)

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
        # Reset original cursor position
        self.set_original_cursor_position()
        self.buf_ref.clear_highlight(self.hl_source)

    def update_highlights(self, highlights):
        self.buf_ref.update_highlights(self.hl_source, highlights, clear=True)

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
            self.main_win.cursor = cursor_pos
        self.update_highlights()

    def draw(self):
        """ Draw function of the plugin """
        ret = self.aj.draw()
        self.log(ret)
        self.buf_ref[:] = ret['lines'][:]
        self.update_highlights(ret['highlights'])
        if ret['top_line'][0] > 0:
            self.set_top_pos(ret['top_line'])
        self.set_cursor_position(ret['cursor_position'])

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

    def resume(self):
        # Check if we have jumped or not
        if not self.has_searched:
            return

        # Sample positions
        window = self.nvim.current.window
        self.current_pos = window.cursor
        self.og_pos = window.cursor
        self.nvim.command('normal! H')
        self.top_pos = window.cursor

        # Spawn the filter buffer
        self.open_aerojump_filter_buf()
        # Spawn the aerojump buffer
        self.open_aerojump_buf()

        # Paste the lines of the old buffer to the new
        new_buf = self.nvim.current.buffer
        new_buf[:] = self.og_buf[:]

        # Restore main win
        self.main_win = self.nvim.current.window

        # Go back to the input buffer window
        self.nvim.command('wincmd j')
        self.nvim.current.window.height = 1
        self.nvim.command("startinsert!")

        # Recreate old state
        self.nvim.current.buffer[0] = self.filter_string
        self.nvim.command("normal! $")

        self.create_keymap()

    # Aerojump Commands
    #====================
    @neovim.autocmd("TextChangedI", pattern='AerojumpFilter', sync=True)
    def insert_changed(self):
        """ Process filter input """
        if self.filter_string == self.nvim.current.line:
            return
        self.filter_string = self.nvim.current.line
        self.apply_filter(self.filter_string)
        self.draw()

    @neovim.command("AerojumpResumeNext", range='', nargs='*', sync=True)
    def AerojumpResumeNext(self, args, range):
        self.resume()
        self.AerojumpSelNext('','')

    @neovim.command("AerojumpResumePrev", range='', nargs='*', sync=True)
    def AerojumpResumePrev(self, args, range):
        self.resume()
        self.AerojumpSelPrev('','')

    @neovim.command("Aerojump", range='', nargs='*', sync=True)
    def Aerojump(self, args, range):
        self.has_searched = True
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

        # Sample current filetype
        resp = get_output_of_vim_cmd(self.nvim, 'set filetype?')
        self.ft = resp.split('=')[1]

        # Spawn the filter buffer
        self.open_aerojump_filter_buf()

        # Spawn the aerojump buffer
        self.open_aerojump_buf()

        # Reference to the aerojump buffer
        self.buf_ref = self.nvim.current.buffer

        # Create lines
        self.aj = self.create_aerojumper(self.og_buf, self.og_pos, self.top_pos, self.window_height)

        # Update position
        self.main_win = self.nvim.current.window

        # Go back to the input buffer window
        self.nvim.command('wincmd j')
        self.nvim.current.window.height = 1
        self.nvim.command("startinsert!")

        # Reset the filter string
        self.filter_string = ''
        self.draw()

        # Create keymap
        self.create_keymap()

    @neovim.command("AerojumpShowLog", range='', nargs='*', sync=True)
    def AerojumpShowLog(self, args, range):
        self.nvim.command('e Aerojump_log')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=aerojump_log')
        self.nvim.current.buffer.append(self.logstr)
        aj_log = self.aj.get_log()
        self.nvim.current.buffer.append('== Aerojump log ==')
        for l in aj_log: self.nvim.current.buffer.append(l)

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

        # TODO Changed my mind, will introduce two new mappings
        # (al, ah) to summon next/prev match again using memory
        # instead which will go to next matches using aerojump
        if self.has_filter:
            pos = self.get_current_cursor()
        else:
            pos = self.current_pos

        # Depending on mode, restore window pos too
        # to match position in filter
        window = self.main_win
        og_pos = window.cursor
        self.nvim.current.window = window
        self.nvim.command('normal! H')
        top_pos = window.cursor

        self.AerojumpExit('', '')

        # Depending on mode, restore window pos too
        # to match position in filter
        self.set_cursor_position(top_pos, og_pos)

        self.nvim.current.window.cursor = pos

    @neovim.command("AerojumpExit", range='', nargs='*', sync=True)
    def AerojumpExit(self, args, range):
        self.nvim.command('stopinsert')
        self.nvim.current.buffer = self.og_buf
        self.nvim.command('bd %s' % self.aerojump_buf_num)
        self.nvim.command('bd %s' % self.filt_buf_num)
        # Restore original position
        self.set_cursor_position(self.top_pos, self.og_pos)
        self.nvim.current.window.cursor = self.og_pos

