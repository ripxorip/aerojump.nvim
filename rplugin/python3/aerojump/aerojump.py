# ============================================================================
# FILE: aerojump.py
# AUTHOR: Philip Karlsson Gisslow <philipkarlsson at me.com>
# License: MIT license
# ============================================================================

# ============================================================================
# = Current TODO =
# 1. Improve the way search results are filtered
#  (reward closeness in a better way) (done?!)
# ============================================================================

# Aerojump classes
# ====================


class AerojumpLine(object):
    """ Class for a line in a aerojump buffer """
    def __init__(self, line, num):
        """ Constructor for the aerojump line class

        Parameters:
            line: the text that the line contains
            num: the line number in the buffer that the line comes from

        Returns:
            Aerojump line object
        """
        # Raw text
        self.raw = line
        self.raw_lower = line.lower()
        # Line number
        self.num = num
        # Matches in this line
        self.matches = []

    def _score_matches(self, matches, pat_len):
        """ Scores the matches depending on how
            many characters that are adjacent to each other

        Parameters:
            matches: List of matches to calculate score for
            pat_len: Total length of the pattern that has been matched

        Returns:
            sorted_matches: List of scored matches
        """

        sorted_matches = []
        self.scores = []
        for m in matches:
            i = 0
            score = 1
            while i < len(m):
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

    def _match_from(self, matches, pattern, pat_index, word_index):
        """ Tries to match character at pattern[pat_index]
            from left to right recursively

        Parameters:
            matches: List of matches
            pattern: Filter pattern
            pat_index: Index in the pattern
            word_index: Word in the line

        Returns:
            Wether or not a full match of the pattern has been accomplished
        """
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
                    return self._match_from(
                            matches, pattern, next_pat_index, next_word_index)
                # No more characters left to process but pattern is complete
                else:
                    return False
        return False

    def filter(self, pattern):
        """ Applies filter to the line

        Parameters:
            pattern: Filter pattern

        Returns:
            n/a
        """
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
                if self._match_from(proposed_matches, pattern, 0, i):
                    self.matches.append(proposed_matches)

        # 1.0 equals full match, thereafter fuzzy partials
        self._score_matches(self.matches, len(pattern))

        # Sorting example for future reference, the parent class
        # matches[:] = sorted_matches[:]
        # matches = matches.sort(key=len, reverse=True)


class Aerojump(object):
    """ The main class of aerojump """
    def __init__(
            self, settings, lines, lin_nums, cursor_pos, top_line, num_lines):
        """ Constructor for the aerojump class

        Parameters:
            settings:   dict of settings
            lines:      array of the lines of a buffer
            lin_nums:   array of the lin_nums for
                        each line in 'line'
            cursor_pos: cursor position when plugin is
                        summoned
            top_line:   top-most line visible in the editor
                        when its summoned
            num_lines:  number of currently visible lines

        Returns:
            an Aerojump object
        """
        self.settings = settings
        self.log_str = []

        # Store intial cursor/windows potisioning
        self.og_top_line = top_line
        self.og_cursor_pos = cursor_pos
        self.num_lines = num_lines

        self.filter_string = ''
        self.lines = []
        for i in range(0, len(lines)):
            self.lines.append(AerojumpLine(lines[i], lin_nums[i]))

        # Reset indices
        self.cursor_line_index = 0
        self.cursor_match_index = 0
        self.has_filter_results = False

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
            True if we still have filter results otherwise false
        """
        self.filter_string = filter_string
        self.filtered_lines = self._get_filtered_lines(
                filter_string, self.lines)
        self.has_filter_results = len(self.filtered_lines) > 0

        if self.has_filter_results:
            cursor_indices = self._set_cursor_to_best_match()
            self.cursor_line_index = cursor_indices[0]
            self.cursor_match_index = cursor_indices[1]
            self._update_highlights()
            return True
        else:
            return False

    def draw(self):
        """ Draw function of the default mode

        In the future this method shall be implemented differently
        depending on mode

        Parameters:
            n/a

        Returns:
            Dict (lines_to_draw, highlights, cursor_position, top_line):
                lines_to_draw:   content of the lines that shall be drawn
                highlights:      highlights that shall be painted in the editor
                cursor_position: current cursor position
        """

        lines = list(map(lambda x: x.raw, self.lines))
        return {'lines':            lines,
                'highlights':       self.highlights,
                'cursor_position':  self.get_cursor()}

    def get_cursor(self):
        """ Gets the current cursor position

        Parameters:
            n/a

        Returns:
            Tuple containing the current cursor position
        """
        if not self.has_filter_results:
            return self.og_cursor_pos

        line = self.filtered_lines[self.cursor_line_index]
        return (line.num, line.matches[self.cursor_match_index][0]-1)

    def get_final_cursor(self):
        """ Gets the final cursor position
            (Needed since some modes adds/subtracts
             from the filtered buffer)

        Parameters:
            n/a

        Returns:
            Tuple containing the current cursor position
        """
        if not self.has_filter_results:
            return self.og_cursor_pos

        line = self.filtered_lines[self.cursor_line_index]
        return (line.num, line.matches[self.cursor_match_index][0]-1)

    def get_highlights(self):
        """ Returns the current highlights

        Parameters:
            n/a

        Returns:
            Current state of the highlights
        """
        return self.highlights

    def cursor_line_up(self):
        """ Moves cursor upwards to the next matching line

        Call 'get_cursor' to get the new position to get effect

        Parameters:
            n/a

        Returns:
            n/a

        """
        if not self.has_filter_results:
            return
        self.cursor_line_index -= 1
        if self.cursor_line_index < 0:
            self.cursor_line_index = 0
        scores = self.filtered_lines[self.cursor_line_index].scores
        self.cursor_match_index = scores.index(max(scores))

        self._update_highlights()

    def cursor_line_down(self):
        """ Moves cursor downward to the next matching line

        Call 'get_cursor' to get the new position to get effect

        Parameters:
            n/a

        Returns:
            n/a

        """
        if not self.has_filter_results:
            return
        self.cursor_line_index += 1
        if self.cursor_line_index >= len(self.filtered_lines):
            self.cursor_line_index = len(self.filtered_lines) - 1
        scores = self.filtered_lines[self.cursor_line_index].scores
        self.cursor_match_index = scores.index(max(scores))

        self._update_highlights()

    def cursor_match_next(self):
        """ Moves cursor towards the next match

        Call 'get_cursor' to get the new position to get effect

        Parameters:
            n/a

        Returns:
            n/a

        """
        if not self.has_filter_results:
            return
        self.cursor_match_index += 1
        matches_len = len(self.filtered_lines[self.cursor_line_index].matches)
        if self.cursor_match_index >= matches_len:
            self.cursor_line_down()
        else:
            self._update_highlights()

    def cursor_match_prev(self):
        """ Moves cursor towards the previous match

        Call 'get_cursor' to get the new position to get effect

        Parameters:
            n/a

        Returns:
            n/a

        """
        if not self.has_filter_results:
            return
        self.cursor_match_index -= 1
        if self.cursor_match_index < 0:
            self.cursor_line_up()
            matchlen = len(self.filtered_lines[self.cursor_line_index].matches)
            self.cursor_match_index = matchlen - 1
        else:
            self._update_highlights()

    def _log(self, log_str):
        """ Log function for Aerojump

        Parameters:
            log_str: string to be logged

        Returns:
            n/a
        """
        self.log_str.append(str(log_str))

    def _best_match_index_for(self, line):
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

    def _best_cursor_in(self, lines):
        """ Returns the best cursor indices among the lines

        Parameters:
            lines: lines to find the best cursor for

        Returns:
            Tuple containing (line_index, match_index)
                line_index: index for the best line
                match_index: index for the best match of that line
        """
        line = lines[0]
        s_index = self._best_match_index_for(line)
        score = line.scores[s_index]

        for l in lines:
            hyp_s_index = self._best_match_index_for(l)
            # Larger score
            if (
                (l.scores[hyp_s_index] > score) or
                (
                    (l.scores[hyp_s_index] == score) and  # Same score
                    (abs(self.og_cursor_pos[0] - l.num) <  \
                        abs(self.og_cursor_pos[0]-line.num))
                    # But closer to the original cursor position
                )
            ):
                score = l.scores[hyp_s_index]
                s_index = hyp_s_index
                line = l
        return(line.filt_index, s_index)

    def _set_cursor_to_best_match(self):
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
        visible_end = visible_start + self.num_lines  # Might need to add -1?

        # Get visible matches
        visible_matches = list(filter(
                lambda l: l.num >= visible_start and l.num <= visible_end,
                self.filtered_lines
                ))
        if visible_matches != []:
            ret = self._best_cursor_in(visible_matches)
        else:
            ret = self._best_cursor_in(self.filtered_lines)
        return ret

    def _update_highlights(self):
        """ Updates the internal highlights

        NOTE: This function can likely be simplified,
        might only need to look at filtered_lines?

        Parameters:
            n/a

        Returns:
            n/a
        """
        highlights = []
        # Match highlights
        for l in self.filtered_lines:
            for m in l.matches:
                for i in m:
                    highlights.append(('SearchResult', l.num-1, i-1, i))
        # Cursor highlights
        line = self.filtered_lines[self.cursor_line_index]
        matches = line.matches[self.cursor_match_index]
        for m in matches:
            highlights.append(('SearchHighlight', line.num-1, m-1, m))
        self.highlights = highlights

    def _get_filtered_lines(self, filter_string, lines):
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

# Aerojump sub classes (modes)
# ============================


class AerojumpSpace(Aerojump):
    def draw(self):
        """ Draw function of the space mode

        In the future this method shall be implemented differently
        depending on mode

        Parameters:
            n/a

        Returns:
            Dict (lines_to_draw, highlights, cursor_position, top_line):
                lines_to_draw:   content of the lines that shall be drawn
                highlights:      highlights that shall be painted in the editor
                cursor_position: current cursor position
        """

        lines = list(map(self._replace_highlights, self.lines))

        return {'lines':            lines,
                'highlights':       self.highlights,
                'cursor_position':  self.get_cursor()}

    @staticmethod
    def _replace_highlights(line):
        if line.matches != []:
            return line.raw
        else:
            return ' '


class AerojumpMilk(Aerojump):

    def _update_highlights(self):
        """ Updates the internal highlights

        NOTE: This function can likely be simplified,
        might only need to look at filtered_lines?

        Parameters:
            n/a

        Returns:
            n/a
        """
        highlights = []

        for l in self.lines:
            if l not in self.filtered_lines:
                highlights.append(("Comment", l.num-1))
        # Match highlights
        for l in self.filtered_lines:
            for m in l.matches:
                for i in m:
                    highlights.append(('SearchResult', l.num-1, i-1, i))
        # Cursor highlights
        line = self.filtered_lines[self.cursor_line_index]
        matches = line.matches[self.cursor_match_index]
        for m in matches:
            highlights.append(('SearchHighlight', line.num-1, m-1, m))
        self.highlights = highlights


class AerojumpBolt(Aerojump):
    """ Subclass for the Bolt mode """
    def get_cursor(self):
        """ Gets the current cursor position

        Parameters:
            n/a

        Returns:
            Tuple containing the current cursor position
        """
        if not self.has_filter_results:
            return self.og_cursor_pos

        line = self.filtered_lines[self.cursor_line_index]
        return (line.res_line, line.matches[self.cursor_match_index][0]-1)

    def apply_filter(self, filter_string):
        """ Filtering function

        Parameters:

            filter_string: string that will be used as filter

        Returns:
            True if we still have filter results otherwise false

        """
        self.filter_string = filter_string
        self.filtered_lines = self._get_filtered_lines(
                filter_string, self.lines)
        self.has_filter_results = len(self.filtered_lines) > 0

        if self.has_filter_results:
            self.highlights = []
            self._sort_filtered_lines()
            # Already sorted
            self.cursor_line_index = 0
            scores = self.filtered_lines[self.cursor_line_index].scores
            self.cursor_match_index = scores.index(max(scores))
            return True
        else:
            return False

    def draw(self):
        """ Draw function of the space mode

        In the future this method shall be implemented differently
        depending on mode

        Parameters:
            n/a

        Returns:
            Dict (lines_to_draw, highlights, cursor_position, top_line):
                lines_to_draw:   content of the lines that shall be drawn
                highlights:      highlights that shall be painted in the editor
                cursor_position: current cursor position
        """

        lines = []
        line_num = 0
        self.separator_indices = []
        for line in self.filtered_lines:
            # Add separator
            separator = '----------- Line: ' + str(line.num) + ' '
            while (len(separator) < 40):
                separator = separator + '-'
            lines.append(separator)
            self.separator_indices.append(line_num)
            line_num += 1

            # Add lines before
            lines_before_res = self.settings['bolt_lines_before']
            for i in range(0, lines_before_res):
                index = line.num - 1 - lines_before_res + i
                if index > 0:
                    lines.append(self.lines[index].raw)
                    line_num += 1

            lines.append(line.raw)
            line.res_line = line_num + 1

            # Add lines after
            lines_after_res = self.settings['bolt_lines_after']
            for i in range(0, lines_after_res):
                index = line.num + 1 + i
                if index < len(self.lines):
                    lines.append(self.lines[index].raw)
                    line_num += 1
            line_num += 1

        if self.has_filter_results:
            self._update_highlights()

        return {'lines':            lines,
                'highlights':       self.highlights,
                'cursor_position':  self.get_cursor()}

    def _sort_filtered_lines(self):
        """ Sorts the filtered lines depending on score

        Parameters:
            n/a

        Returns:
            n/a
        """
        for f in self.filtered_lines:
            f.best_score = max(f.scores)
        self.filtered_lines.sort(key=lambda x: x.best_score, reverse=True)

    def _update_highlights(self):
        """ Updates the internal highlights

        NOTE: This function can likely be simplified,
        might only need to look at filtered_lines?

        Parameters:
            n/a

        Returns:
            n/a
        """
        highlights = []
        # Match highlights
        for l in self.filtered_lines:
            for m in l.matches:
                for i in m:
                    highlights.append(('SearchResult', l.res_line-1, i-1, i))
        # Cursor highlights
        line = self.filtered_lines[self.cursor_line_index]
        matches = line.matches[self.cursor_match_index]
        for m in matches:
            highlights.append(('SearchHighlight', line.res_line-1, m-1, m))
        # Separators
        for s in self.separator_indices:
            highlights.append(('Comment', s))
        self.highlights = highlights
