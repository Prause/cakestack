import curses
from datetime import datetime, timezone
import re
import math

ERROR_RE=re.compile(r'error|fail', re.IGNORECASE)

def pretty_timediff(t_delta):
    s = t_delta.total_seconds()
    f_str = ''

    minutes = int(s/60)
    seconds = s - minutes * 60

    hours = int(minutes/60)
    minutes -= hours * 60

    days = int(hours/24)
    hours -= days * 24

    if s < 60:
        f_str = "{:.3f} seconds ago".format(s)

    if s >= 60:
        f_str = "{:2d}m {:6.3f}s ago".format(minutes, seconds)

    if s >= 3600:
        f_str = "{:2d}h {}".format(hours, f_str)

    if s >= 3600 * 24:
        f_str = "{}d {}".format(days, f_str)

    return "{:>22s}".format(f_str)

class CursedViewer():
    def __init__(self):
        self.stdscr = None
        self.scroll_pos = None
        self.date_mode = None
        self.filter = None
        self.file_filter = None
        self.wrap = None
        self.debug = None
        self.search_string = None
        self.search_string_type = False

    def __enter__(self):
        self.stdscr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        self.stdscr.keypad(True)
        self.stdscr.nodelay(True)
        curses.start_color()
        if curses.can_change_color():
            curses.init_color(3, 0, 900, 600)
            curses.init_color(4, 900, 900, 0)
            curses.init_color(5, 900, 600, 0)
        curses.init_pair(1, 3, curses.COLOR_BLACK)
        curses.init_pair(2, 4, curses.COLOR_BLACK)
        curses.init_pair(3, 5, curses.COLOR_BLACK)
        return self

    def __exit__(self, type, value, traceback):
        self.stdscr.clear()
        curses.nocbreak()
        self.stdscr.keypad(False)
        curses.echo()
        curses.endwin()
        if self.debug:
            print(self.debug)
        print('scroll_pos', self.scroll_pos)
        print('pairs', curses.COLOR_PAIRS)
        print('colors', curses.COLORS)


    def get_filtered_lines(self,lines):
        if not self.filter and not self.search_string:
            return lines

        # TODO maybe filter backwards until number of lines == curses.LINES ?)
        stage_1 = [l for l in lines if not self.filter or l.get('type') == self.filter]
        stage_2 = [l for l in stage_1 if not self.search_string or self.search_string in l.get('line', '')]
        return stage_2

    def render(self, content):
        lines = self.get_filtered_lines(content.lines)
        idx_start = max(0, len(lines) - curses.LINES) if self.scroll_pos == None else self.scroll_pos
        self.stdscr.erase()
        now = datetime.now()

        i = 0
        i_screen = 0
        while i < min(len(lines) - idx_start, curses.LINES) and i_screen < curses.LINES:
            # |curses.A_BOLD|curses.A_BLINK
            l = lines[idx_start+i]

            flag = None
            if l.get('type') == 'stdout':
                flag = curses.color_pair(1)
            if ERROR_RE.search(l.get('line', '')):
                flag = curses.color_pair(2)
            if l.get('type') == 'stderr':
                flag = curses.color_pair(3)

            ts = ''
            d = l.get('date')
            if self.date_mode and d:
                if self.date_mode == 'sec':
                    ts = d.strftime('%s')
                elif self.date_mode == 'utc':
                    ts = d.isoformat(sep=' ', timespec='milliseconds')
                elif self.date_mode == 'diff':
                    diff = now - d
                    ts = pretty_timediff(diff)
                ts += ' | '

            msg = ts + l.get("line", '')
            # TODO preserve colors
            msg = re.sub('\u001b\[\d+(;\d)?m', '', msg)
            try:
                if self.wrap:
                    num_msg_lines = math.ceil(len(msg) / curses.COLS)
                    for l_i in range(0, num_msg_lines):
                        i_screen += 1
                        self.stdscr.addstr(i_screen-1, 0, msg[(l_i*curses.COLS):((l_i+1)*curses.COLS)], flag)
                        #self.stdscr.addstr(i_screen-1, 0, str(i_screen), flag)
                else:
                    i_screen += 1
                    self.stdscr.addstr(i_screen-1, 0, msg[:curses.COLS], flag)
            except Exception as e:
                self.debug = e

            i += 1



        status_bar = []
        if self.filter:
            status_bar += [self.filter]
        if self.scroll_pos:
            status_bar += ['scrolling']
        elif self.scroll_pos == 0:
            status_bar += ['top']
        if self.wrap:
            status_bar += [self.wrap]
            #status_bar += [str(i),str(i_screen)]
        if self.search_string:
            status_bar += ['search: ' + self.search_string]

        if status_bar:
            self.stdscr.addstr(0, 0, ' ' + ' | '.join(status_bar) + ' ')
        self.stdscr.refresh()


    def move_page(self, total_lines, delta_lines):
        if self.scroll_pos == None:
            self.scroll_pos = max(total_lines - curses.LINES, 0)

        if delta_lines < 0:
            self.scroll_pos = max(self.scroll_pos + delta_lines, 0)

        if delta_lines > 0:
            max_pos = max(total_lines-1, 0)
            self.scroll_pos = min(self.scroll_pos + delta_lines, max_pos)

    def process_events(self, content):
        c = self.stdscr.getch()
        events = []
        lines = content.lines
        if c >= 0:
            lines = self.get_filtered_lines(content.lines)

        while c >= 0:
            events += ['update']
            if c == ord('q'):
                curses.flash()
                return ['quit']

            if c == ord('r') or c == ord('G'):
                self.scroll_pos = None
                self.search_string_type = False
                self.search_string = None
            if c == ord('g'):
                self.scroll_pos = 0

            if c == ord('K') or c == curses.KEY_PPAGE:
                self.move_page(len(lines), -curses.LINES)
            if c == ord('J') or c == curses.KEY_NPAGE:
                self.move_page(len(lines), curses.LINES)

            if c == ord('k') or c == curses.KEY_UP:
                self.move_page(len(lines), -1)
            if c == ord('j') or c == curses.KEY_DOWN:
                self.move_page(len(lines), +1)

            if c == ord('f'):
                if not self.filter:
                    self.filter = 'stderr'
                elif self.filter == 'stderr':
                    self.filter = 'stdout'
                else:
                    self.filter = None

            if c == ord('e'):
                if not self.wrap:
                    self.wrap = 'wrap'
                else:
                    self.wrap = None

            if c == ord('t'):
                if not self.date_mode:
                    self.date_mode = 'sec'
                elif self.date_mode == 'sec':
                    self.date_mode = 'utc'
                elif self.date_mode == 'utc':
                    self.date_mode = 'diff'
                else:
                    self.date_mode = None

            if c == ord('/'):
                if not self.search_string_type:
                    self.search_string_type = True
                    self.search_string = "getCurrentPerson"
                else:
                    self.search_string_type = False

            if c == curses.KEY_RESIZE:
                curses.update_lines_cols()

            c = self.stdscr.getch()
        return events
