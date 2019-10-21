# ============================================================================
# FILE: __init__.py
# AUTHOR: Philip Karlsson Gisslow <philipkarlsson at me.com>
# License: MIT license
# ============================================================================

import neovim

from aerojump.aerojump import Aerojump, AerojumpSpace, AerojumpBolt, \
    AerojumpMilk


def get_output_of_vim_cmd(nvim, cmd):
    """ Utility function to get the current output
        of a vim command

    Parameters:
        nvim: Neovim instance
        cmd: Command to fetch output from

    Returns:
        n/a
    """
    nvim.command('redir @a')
    nvim.command(cmd)
    nvim.command('redir END')
    return nvim.eval('@a').strip('\n')


@neovim.plugin
class AerojumpNeovim(object):
    def __init__(self, nvim):
        self.nvim = nvim
        self.logstr = []
        self.logstr.append('== Aerojump debug ==')
        self.has_searched = False
        self.default_keymaps = {
            "<C-h>": "AerojumpSelPrev",
            "<Left>": "AerojumpSelPrev",
            "<C-j>": "AerojumpDown",
            "<Down>": "AerojumpDown",
            "<C-k>": "AerojumpUp",
            "<Up>": "AerojumpUp",
            "<C-l>": "AerojumpSelNext",
            "<Right>": "AerojumpSelNext",
            "<C-q>": "AerojumpExit",
            "<ESC>": "AerojumpSelect",
            "<CR>": "AerojumpSelect",
            "<Space>": "AerojumpSelect",
        }

    def __log(self, s):
        self.logstr.append(str(s))

    def __open_aerojump_buf(self):
        self.nvim.command('split Aerojump')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=aerojump')
        # Fix filetype in order to keep old syntax
        self.nvim.command('set filetype='+self.ft+'.aerojump')
        self.aerojump_buf_num = self.nvim.current.buffer.number

    def __open_aerojump_filter_buf(self, filter_string=''):
        if self.uses_tabs:
            self.nvim.command('tabedit AerojumpFilter')
        else:
            self.nvim.command('edit AerojumpFilter')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=AerojumpFilter')
        if filter_string != '':
            # TODO Idea: Maybe add some special characters
            # like regexp to enforce whole matches only?
            self.nvim.current.buffer[0] = filter_string
        self.filt_buf_num = self.nvim.current.buffer.number

    def __set_cursor_position(self, pos):
        old_win = self.nvim.current.window
        self.nvim.current.window = self.main_win
        self.nvim.current.window.cursor = pos
        self.nvim.current.window = old_win

    def __set_top_pos(self, top_pos):
        old_win = self.nvim.current.window
        self.nvim.current.window = self.main_win
        self.nvim.current.window.cursor = top_pos
        self.nvim.command('normal! zt')
        self.nvim.current.window = old_win

    def __create_aerojumper(
            self, settings, lines, cursor_pos, top_line, num_lines):
        lin_nums = list(range(1, len(lines) + 1))
        if settings['mode'] == 'space':
            return AerojumpSpace(
                    settings, lines, lin_nums, cursor_pos, top_line, num_lines)
        elif settings['mode'] == 'milk':
            return AerojumpMilk(
                    settings, lines, lin_nums, cursor_pos, top_line, num_lines)
        elif settings['mode'] == 'bolt':
            settings['bolt_lines_before'] = 1
            settings['bolt_lines_after'] = 1
            return AerojumpBolt(
                    settings, lines, lin_nums, cursor_pos, top_line, num_lines)
        else:
            return Aerojump(
                    settings, lines, lin_nums, cursor_pos, top_line, num_lines)

    def __update_highlights(self, highlights):
        self.buf_ref.update_highlights(self.hl_source, highlights, clear=True)

    def __draw(self):
        if self.filter_string != '':
            # Draw aerojump output
            ret = self.aj.draw()
            self.buf_ref[:] = ret['lines'][:]
            self.__update_highlights(ret['highlights'])
            self.__set_cursor_position(ret['cursor_position'])
        else:
            # Draw unfiltered output
            self.buf_ref[:] = self.og_lines[:]
            self.__set_top_pos(self.top_pos)
            self.__set_cursor_position(self.og_pos)

    def __create_keymap(self):
        keymaps = self.default_keymaps.copy()
        keymaps.update(self.nvim.vars.get("aerojump_keymaps", {}))
        for k in keymaps:
            self.nvim.command(f"inoremap <buffer> {k} <ESC>:{keymaps[k]}<CR>")

    def __resume(self):
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
        self.__open_aerojump_filter_buf()
        # Spawn the aerojump buffer
        self.__open_aerojump_buf()

        # Paste the lines of the old buffer to the new
        new_buf = self.nvim.current.buffer
        new_buf[:] = self.og_lines[:]

        # Restore main win
        self.main_win = self.nvim.current.window

        # Go back to the input buffer window
        self.nvim.command('wincmd j')
        self.nvim.current.window.height = 1
        self.nvim.command("startinsert!")

        # Recreate old state
        self.nvim.current.buffer[0] = self.filter_string
        self.nvim.command("normal! $")

        self.__create_keymap()

    # Aerojump Commands
    # ====================
    @neovim.autocmd("TextChangedI", pattern='AerojumpFilter', sync=True)
    def insert_changed(self):
        """ Autocmd for when text changes

        Parameters:
            n/a

        Returns:
            n/a
        """
        if self.filter_string == self.nvim.current.line:
            return
        self.filter_string = self.nvim.current.line
        has_res = self.aj.apply_filter(self.filter_string)
        if has_res:
            self.__draw()
        else:
            # Erase the last character
            self.filter_string = self.filter_string[:-1]
            self.nvim.current.line = self.filter_string

    @neovim.command("AerojumpResumeNext", range='', nargs='*', sync=True)
    def AerojumpResumeNext(self, args, range):
        """ Resumes aerojump from previous matches selecting the next match

        Parameters:
            n/a

        Returns:
            n/a
        """
        self.__resume()
        self.AerojumpSelNext('', '')

    @neovim.command("AerojumpResumePrev", range='', nargs='*', sync=True)
    def AerojumpResumePrev(self, args, range):
        """ Resumes aerojump from previous matches selecting the previous match

        Parameters:
            n/a

        Returns:
            n/a
        """
        self.__resume()
        self.AerojumpSelPrev('', '')

    @neovim.command("Aerojump", range='', nargs='*', sync=True)
    def Aerojump(self, args, range):
        """ Start aerojump in its default (or last?) mode

        Parameters:
            args[0]: Where to take the initial input from
                     - 'kbd' means using regular filter input
                     - 'cursor' means symbol under cursor
            args[1]: Mode that aerojump will start in

        Returns:
            n/a
        """
        self.uses_tabs = self.nvim.vars.get("aerojump_uses_tabs")
        filter_string = ''
        settings = {}
        settings['input'] = args[0]
        settings['mode'] = args[1]

        if settings['input'] == 'cursor':
            filter_string = self.nvim.eval('expand(\'<cword>\')').strip('\n')

        self.has_searched = True
        self.has_filter = False
        self.hl_source = self.nvim.new_highlight_source()
        self.og_buf = self.nvim.current.buffer
        self.og_lines = self.nvim.current.buffer[:]
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
        self.__open_aerojump_filter_buf(filter_string)

        # Spawn the aerojump buffer
        self.__open_aerojump_buf()

        # Reference to the aerojump buffer
        self.buf_ref = self.nvim.current.buffer

        # Create lines
        self.aj = self.__create_aerojumper(
                settings, self.og_lines, self.og_pos,
                self.top_pos, self.window_height
                )

        # Update position
        self.main_win = self.nvim.current.window

        # Go back to the input buffer window
        self.nvim.command('wincmd j')
        self.nvim.current.window.height = 1
        self.nvim.command("startinsert!")

        # Reset the filter string
        self.filter_string = ''
        self.__draw()

        # Create keymap
        self.__create_keymap()

    @neovim.command("AerojumpShowLog", range='', nargs='*', sync=True)
    def AerojumpShowLog(self, args, range):
        """ Show the aerojump log

        Parameters:
            n/a

        Returns:
            n/a
        """
        self.nvim.command('e Aerojump_log')
        self.nvim.command('setlocal buftype=nofile')
        self.nvim.command('setlocal filetype=aerojump_log')
        self.nvim.current.buffer.append(self.logstr)
        self.nvim.current.buffer.append('== Aerojump log ==')
        self.nvim.current.buffer.extend(self.aj.get_log())

    @neovim.command("AerojumpUp", range='', nargs='*', sync=True)
    def AerojumpUp(self, args, range):
        """ Go up one line of matches

        Parameters:
            n/a

        Returns:
            n/a
        """
        self.aj.cursor_line_up()
        # TODO: [Performance] Incremental update of highlights?
        self.__update_highlights(self.aj.get_highlights())
        self.main_win.cursor = self.aj.get_cursor()

        self.nvim.command('startinsert')
        self.nvim.command('normal! $')

    @neovim.command("AerojumpDown", range='', nargs='*', sync=True)
    def AerojumpDown(self, args, range):
        """ Go down one line of matches

        Parameters:
            n/a

        Returns:
            n/a
        """
        self.aj.cursor_line_down()
        # TODO: [Performance] Incremental update of highlights?
        self.__update_highlights(self.aj.get_highlights())
        self.main_win.cursor = self.aj.get_cursor()

        self.nvim.command('startinsert')
        self.nvim.command('normal! $')

    @neovim.command("AerojumpSelNext", range='', nargs='*', sync=True)
    def AerojumpSelNext(self, args, range):
        """ Select the next match

        Parameters:
            n/a

        Returns:
            n/a
        """
        self.aj.cursor_match_next()
        # TODO: [Performance] Incremental update of highlights?
        self.__update_highlights(self.aj.get_highlights())
        self.main_win.cursor = self.aj.get_cursor()

        self.nvim.command('startinsert')
        self.nvim.command('normal! $')

    @neovim.command("AerojumpSelPrev", range='', nargs='*', sync=True)
    def AerojumpSelPrev(self, args, range):
        """ Select the previous match

        Parameters:
            n/a

        Returns:
            n/a
        """
        self.aj.cursor_match_prev()
        # TODO: [Performance] Incremental update of highlights?
        self.__update_highlights(self.aj.get_highlights())
        self.main_win.cursor = self.aj.get_cursor()

        self.nvim.command('startinsert')
        self.nvim.command('normal! $')

    @neovim.command("AerojumpSelect", range='', nargs='*', sync=True)
    def AerojumpSelect(self, args, range):
        """ Select the current match and move the cursor there

        Parameters:
            n/a

        Returns:
            n/a
        """
        cursor = self.aj.get_final_cursor()

        # Sample position in aj window
        window = self.main_win
        self.nvim.current.window = window
        self.nvim.command('normal! H')
        top_pos = window.cursor

        self.AerojumpExit('', '')

        self.nvim.current.window.cursor = top_pos
        self.nvim.command('normal! zt')
        # Doing it this way respects jump stack
        self.nvim.command('normal! ' + str(cursor[0]) + 'G')
        self.nvim.command('normal! ' + str(cursor[1]+1) + '|')

    @neovim.command("AerojumpExit", range='', nargs='*', sync=True)
    def AerojumpExit(self, args, range):
        """ Exit aerojump without moving the selection

        Parameters:
            n/a

        Returns:
            n/a
        """
        self.nvim.command('stopinsert')
        self.nvim.current.buffer = self.og_buf
        self.nvim.command('bwipeout %s' % self.aerojump_buf_num)
        self.nvim.command('bwipeout %s' % self.filt_buf_num)
        if self.uses_tabs:
            self.nvim.command('tabclose')
        # Restore original position
        self.nvim.current.window.cursor = self.top_pos
        self.nvim.command('normal! zt')
        self.nvim.current.window.cursor = self.og_pos
