import os
import time
from datetime import datetime, timedelta
import re
from logs.viewer import CursedViewer


LOG_DATE_RE=re.compile(r'(^|\|\s*)[A-Z]+\s+(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z)') # DEBUG 2020-04-01T11:35:21.460Z |
TS_DATE_RE=re.compile(r'^([a-zA-Z]{3} \d{2} \d{2}:\d{2}:\d{2}) ?(.*)')
DATE_PARSE="%b %d %H:%M:%S"

TS2_DATE_RE=re.compile(r'^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(\.\d+)?Z ?(.*)') # 2020-04-01T11:35:21.460Z
DATE_PARSE_2="%Y-%m-%dT%H:%M:%S"


class LogFileTailer():
    def __init__(self, files):
        self.files = files

    def __enter__(self):
        for f in self.files:
            try:
                f["fh"] = open(f["f_name"])
            except Exception as e:
                print('ignoring file {}:'.format(f.get("f_name")), e)
        return self

    def __exit__(self, type, value, traceback):
        print("closing files")
        for f in self.files:
            if f.get("fh"):
                try:
                    f["fh"].close()
                except Exception as e:
                    print("failed closing file", f.get("f_name"))
                    print(e)

    def new_lines(self):
        for f in self.files:
            if not f.get("fh"):
                continue

            try:
                line = f["fh"].readline().strip()
                while line:
                    m = LOG_DATE_RE.match(line)
                    if m: 
                        pass
                    m = TS2_DATE_RE.match(line)
                    if m:
                        l = m.group(3)
                        d = datetime.strptime(m.group(1), DATE_PARSE_2).replace(year=f["last_time"].year)
                        if( m.group(2) ):
                            seconds = float("0" + m.group(2))
                            d += timedelta(seconds=seconds)
                        yield { 'line': l, 'date': d, 'type': f['type'], 'instance': f['f_name'] }
                    else:
                        yield { 'line': line, 'type': f['type'], 'instance': f['f_name'], 'date': f['last_time'] }
                    line = f["fh"].readline().strip()

            except Exception as e:
                #print('closing file {}'.format(f["f_name"]), e)
                print(e)
                f["fh"].close()
                f["fh"] = None
        return


class LogFilter():
    def __init__(self):
        self.files = []
        self.lines = []

    def add_stdout(self, f_name):
        if os.path.isfile(f_name):
            base_time = datetime.fromtimestamp(os.path.getctime(f_name))
        else:
            base_time = datetime.utcnow()
        self.files += [{ "f_name": f_name, "type": "stdout", 'last_time': base_time }]

    def add_stderr(self, f_name):
        if os.path.isfile(f_name):
            base_time = datetime.fromtimestamp(os.path.getctime(f_name))
        else:
            base_time = datetime.utcnow()
        self.files += [{ "f_name": f_name, "type": "stderr" , 'last_time': base_time }]

    def show(self):
        err = None
        keep_looping = True
        do_update = False

        with LogFileTailer(self.files) as tailer:
            with CursedViewer() as cursed_viewer:
                while keep_looping:
                    events = cursed_viewer.process_events(self)
                    if 'quit' in events:
                        break

                    if 'update' in events:
                        do_update = True
                    else:
                        do_update = False

                    new_lines = []
                    for line in tailer.new_lines():
                        new_lines += [line]

                    if new_lines or do_update:
                        new_lines.sort(key=lambda d: d['date'])
                        self.lines += new_lines
                        cursed_viewer.render(self)
                    else:
                        time.sleep(0.1)
