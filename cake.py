#!/usr/bin/env python3

import os
import datetime
import signal
import psutil
import yaml
import json
import subprocess

class Service:

    config_all = {} # lazy-loaded config for all services
    DEFAULT_RUN_DIR='$HOME/.cakestack/run'
    CAKESTACK_DIR='$HOME/.cakestack'


    def with_conf(f):
        def helper(self, *args):
            # TODO if not self.config ???
            if not type(self).config_all:
                type(self).read_config()
            self.config = type(self).config_all[self.tag]
            self.entry = self.config.get("entry")
            self.dir = self.config.get("dir")
            self.git = self.config.get("git")
            self.exit = self.config.get("exit")
            self.revision = self.config.get("revision")
            return f(self, *args)
        return helper


    @staticmethod
    def read_config():
        conf_file = os.path.expandvars( os.path.join( Service.CAKESTACK_DIR, "config.yaml"))
        if not os.path.isfile( conf_file ):
            print("Config file not found", conf_file)
            return {}
        with open( conf_file ) as f:
            Service.config_all = yaml.load( f.read() )
        return Service.config_all


    def __init__(self, tag):
        self.tag = tag
        self.config = {}


    def get_active_dir(self):
        # if currently running, return currently running dir, else None
        return None


    @with_conf
    def get_working_dir(self):
        if self.dir:
            return os.path.expandvars(self.dir)

        # for other modes, we need the tag_run_dir:
        tag_run_dir = self.create_run_dirs()
        if not tag_run_dir:
            raise Exception( "Could not find or create working dir:", self.tag )

        if self.git:
            repo_dir = os.path.join(tag_run_dir, 'repo')

            commit_hash = None
            if self.revision:
                commit_hash = self.revision

            else:
                latest_file = os.path.join( repo_dir, 'latest' )
                if not os.path.isfile(latest_file):
                    raise Exception( "No latest commit hash found, skipping:", self.tag )

                with open( latest_file ) as f:
                    commit_hash = f.readline().strip()

            w_dir = os.path.join( repo_dir, commit_hash )
            if not os.path.isdir(w_dir):
                raise Exception( "No commit dir found, skipping:", self.tag )
            return w_dir

        return tag_run_dir


    def running(self):
        if self.get_root_proc():
            return True
        return False


    def start(self):
        if not self.running():
            return self.start_command()


    @with_conf
    def stop(self):
        # TODO in case of self.exit, check that pid is gone
        # TODO delete pid file
        if self.exit:
            # this executes the exit command in the (new) working dir.
            w_dir = self.get_working_dir()
            return subprocess.Popen(self.exit, cwd=w_dir, shell=True).wait()

        procs = self.get_procs()
        for p in procs:
            p.send_signal(signal.SIGTERM)
        return psutil.wait_procs(procs, timeout=180)


    @with_conf
    def is_up_to_date(self):
        ## checks whether currently running version is up to date with config
        proc_file = os.path.expandvars( os.path.join( type(self).DEFAULT_RUN_DIR, self.tag, "proc.json" ) )
        if not os.path.isfile( proc_file ):
            return False
        with open( proc_file, 'r' ) as pf:
            active_conf = json.loads( pf.read() )
            if active_conf.get('entry') != self.entry:
                return False
            if active_conf.get('cwd') != self.get_working_dir():
                return False
        return True


    def get_pid(self):
        pid_file = os.path.expandvars( os.path.join( type(self).DEFAULT_RUN_DIR, self.tag, "pid" ) )
        if not os.path.isfile( pid_file ):
            print( "No pid file found for", self.tag )
            return

        with open( pid_file ) as f:
            pid_string = f.read()
            if pid_string:
                return int( pid_string )


    def get_root_proc(self):
        pid = self.get_pid()
        if not pid:
            return
        try:
            return psutil.Process(pid)
        except psutil.NoSuchProcess:
            print( "No process found for", self.tag )
            return


    def get_procs(self):
        parent = self.get_root_proc()
        if not parent:
            return []

        children = parent.children(recursive=True)
        children += [parent]
        return children


    @with_conf
    def create_run_dirs(self):
        tag_run_dir = os.path.abspath( os.path.expandvars( os.path.join( type(self).DEFAULT_RUN_DIR, self.tag ) ) )
        if not check_and_create_dir( tag_run_dir ):
            print("Error: Failed creating run dir!", tag_run_dir)
            return
        return tag_run_dir


    @with_conf
    def start_command(self):
        if not self.entry:
            print( "No entry point defined:", self.tag, ", doing nothing." )
            return
        print( "starting...", self.tag )

        w_dir = self.get_working_dir()
        tag_run_dir = self.create_run_dirs()
        if not tag_run_dir:
            return

        with open( os.path.join(tag_run_dir, "pid"), 'w' ) as f:
            err_file = os.path.join(tag_run_dir, "err.log")
            out_file = os.path.join(tag_run_dir, "out.log")
            exit_file = os.path.join(tag_run_dir, "exit")
            proc_file = os.path.join(tag_run_dir, "proc.json")
            f_err = open( err_file, 'a' )
            f_out = open( out_file, 'a' )
            now = datetime.datetime.utcnow().isoformat() + 'Z'
            print( "starting at " + now, file=f_out )
            print( "starting at " + now, file=f_err )

            cmd = self.entry + "; echo $? > " + exit_file
            process = subprocess.Popen(cmd, cwd=w_dir, shell=True, stdout=f_out, stderr=f_err)
            f.write(str(process.pid))
            with open( proc_file, 'w' ) as pf:
                print( json.dumps({
                    'cwd':w_dir,
                    'cmd':cmd,
                    'entry':self.entry,
                    'started':now
                    }), file=pf )
            return process.pid


def check_and_create_dir( dst ):
    if os.path.isfile( dst ):
        print( "Error: dir already exists and is a file", dst )
        return False
    if not os.path.isdir( dst ):
        print( "creating dir", dst )
        os.makedirs( dst )
    return True
