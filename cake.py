#!/usr/bin/env python3

import random
import string
import os
import datetime
import time
import signal
import psutil
import shutil
import yaml
import json
import subprocess

def mode(filename):
    return oct(os.stat(filename).st_mode & 0o777)[-3:]


def check_and_create_dir( dst ):
    if os.path.isfile( dst ):
        print( "Error: dir already exists and is a file", dst )
        return False
    if not os.path.isdir( dst ):
        print( "creating dir", dst )
        os.makedirs( dst )
    return True

def generate_instance_id():
    return ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))

class ConfigProvider:
    config_all = None # lazy-loaded config for all services
    instances = None

    @classmethod
    def get_instances(cls):
        if cls.instances == None:
            cls.instances = cls.load_instances()
        return cls.instances

    @staticmethod
    def load_instances():
        instances_dir = os.path.expandvars(Service.DEFAULT_INSTANCE_DIR)
        instance_ids = [d for d in os.listdir(instances_dir) if os.path.isdir(os.path.join(instances_dir, d))]
        instances = {}
        for iid in instance_ids:
            instance_dir = os.path.join( instances_dir, iid )
            proc_file = os.path.join( instance_dir, "proc.json" )
            if os.path.isfile(proc_file):
                with open( proc_file, 'r' ) as f:
                    instances[iid] = json.loads( f.read() )
            else:
                instances[iid] = {}

            stopped_file = os.path.join( instance_dir, "stopped" )
            if os.path.isfile(stopped_file):
                with open( stopped_file, 'r' ) as f:
                    instances[iid]['stopped'] = f.read().strip()

            exit_file = os.path.join( instance_dir, "exit" )
            if os.path.isfile(exit_file):
                with open( exit_file, 'r' ) as f:
                    instances[iid]['exit'] = f.read().strip()
        return instances

    @classmethod
    def get_config(cls):
        if cls.config_all == None:
            cls.config_all = cls.read_config()
        return cls.config_all

    @staticmethod
    def read_config():
        conf_file = os.path.expandvars( os.path.join( Service.CAKESTACK_DIR, "config.yaml"))
        if not os.path.isfile( conf_file ):
            print("Config file not found", conf_file)
            return {}
        else:
            print("Reading config")
            with open( conf_file ) as f:
                conf = yaml.load(f.read(), Loader=yaml.FullLoader) if yaml.FullLoader else yaml.load(f.read())
                run_dir = os.path.expandvars(Service.DEFAULT_RUN_DIR)
                for tag in conf:
                    instance_list_file = os.path.join(run_dir, tag, "instances")
                    if os.path.isfile( instance_list_file ):
                        with open(instance_list_file, 'r') as f:
                            conf[tag]['instances'] = [iid.strip() for iid in f.readlines()]
                return conf


class Service:

    DEFAULT_RUN_DIR='$HOME/.cakestack/run'
    DEFAULT_INSTANCE_DIR='$HOME/.cakestack/instances'
    CAKESTACK_DIR='$HOME/.cakestack'

    def with_conf(fun):
        def helper(self, *args):
            if self.tag and not self.config:
                self.config = ConfigProvider.get_config().get(self.tag, {})
                self.entry = self.config.get("entry")
                self.dir = self.config.get("dir")
                self.git = self.config.get("git")
                self.exit = self.config.get("exit")
                self.revision = self.config.get("revision")
                if not self.instance_id and 'instances' in self.config and len(self.config['instances']):
                    self.instance_id = self.config['instances'][-1]

            if self.instance_id:
                self.instance_config = ConfigProvider.get_instances().get(self.instance_id, {})
                self.cwd = self.instance_config.get('cwd')
                self.cmd = self.instance_config.get('cmd')
                self.started = self.instance_config.get('started')
                if not self.tag:
                    self.tag = self.instance_config.get('tag')
                if not self.entry:
                    self.entry = self.instance_config.get('entry')
            return fun(self, *args)
        return helper


    def __init__(self, tag=None, instance_id=None):
        self.tag = tag
        self.instance_id = instance_id
        self.config = {}
        self.instance_config = {}
        self.dir = None
        self.git = None
        self.exit = None
        self.revision = None
        self.cwd = None
        self.cmd = None
        self.started = None
        self.entry = None

        if tag and instance_id:
            raise Exception("overdefined service instance")

        if not tag and not instance_id:
            self.dir = os.getcwd()


    @with_conf
    def load_config(self):
        pass

    def set_entry(self, entry):
        if entry[0] == 'sudo':
            entry = ['sudo', '-n'] + entry[1:]
        self.entry = ' '.join(entry)

    @with_conf
    def get_working_dir(self):
        if self.dir:
            return os.path.expandvars(self.dir)

        # for other modes, we need the run_dir:
        run_dir, instance_dir = self.create_run_dirs()
        if not run_dir:
            raise Exception( "Could not find or create working dir:", self.tag )

        if self.git:
            repo_dir = os.path.join(run_dir, 'repo')

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

        return run_dir


    def is_running(self):
        if self.get_root_proc():
            return True
        return False


    def start(self):
        if not self.is_running():
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
        # kill parents first (smaller pid)
        for p in sorted(procs, key=lambda p: p.pid):
            try:
                p.send_signal(signal.SIGTERM)
            except psutil.NoSuchProcess:
                print( "Process {} already terminated".format(p.pid) )

        processes = psutil.wait_procs(procs, timeout=180)

        # wait for loggin to terminate as well
        if procs:
            self.wait_for_logging()

        stop_file = os.path.join( self.get_instance_dir(), "stopped" )
        with open(stop_file, 'w') as f:
            print( datetime.datetime.utcnow().isoformat() + 'Z', file=f)
        return processes


    @with_conf
    def wait_for_logging(self, timeout=10):
        run_dir, instance_dir = self.create_run_dirs()
        out_current = os.path.join(instance_dir, "out.log.d/current")
        err_current = os.path.join(instance_dir, "err.log.d/current")
        if shutil.which('multilog'):
            for i in range(0,timeout):
                out_done = not os.path.isfile(out_current) or mode(out_current) == '744'
                err_done = not os.path.isfile(err_current) or mode(err_current) == '744'
                if out_done and err_done:
                    return True
                print( "Waiting for multilog to terminate" )
                time.sleep(1)
        return False

    @with_conf
    def is_up_to_date(self):
        ## checks whether currently running version is up to date with config
        if self.instance_config.get('entry') != self.entry:
            return False
        if self.instance_config.get('cwd') != self.get_working_dir():
            return False
        return True


    def get_pid(self):
        instance_dir = self.get_instance_dir()
        if not instance_dir:
            return

        pid_file = os.path.join( instance_dir, "pid" )
        if not os.path.isfile( pid_file ):
            print( "No pid file found for", self.instance_id )
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
            #print( "No process found for", self.instance_id )
            return


    def get_procs(self):
        parent = self.get_root_proc()
        if not parent:
            return []

        children = parent.children(recursive=True)
        children += [parent]
        return children

    def get_run_dir(self):
        return os.path.abspath( os.path.expandvars( os.path.join( type(self).DEFAULT_RUN_DIR, self.tag ) ) )

    def get_instance_dir(self):
        if not self.instance_id:
            self.load_config()
        if not self.instance_id:
            return
        return os.path.abspath( os.path.expandvars( os.path.join( type(self).DEFAULT_INSTANCE_DIR, self.instance_id ) ) )

    def get_stdout_file(self):
        return os.path.join( self.get_instance_dir(), "out.log" )

    def get_stderr_file(self):
        return os.path.join( self.get_instance_dir(), "err.log" )

    def create_run_dirs(self):
        if self.tag:
            run_dir = self.get_run_dir()
            if not check_and_create_dir( run_dir ):
                print("Error: Failed creating run dir!", run_dir)
                return
        else:
            run_dir = None

        # FIXME
        instance_dir = self.get_instance_dir()
        if not check_and_create_dir( instance_dir ):
            print("Error: Failed creating instance dir!", instance_dir)
            return
        return run_dir, instance_dir


    @with_conf
    def start_command(self):
        if not self.entry:
            print( "No entry point defined: {}, doing nothing.".format(self.tag) )
            return
        print( "starting...", self.tag if self.tag else self.entry )

        self.instance_id = generate_instance_id()

        w_dir = self.get_working_dir()
        run_dir, instance_dir = self.create_run_dirs()
        if not instance_dir:
            return

        if run_dir:
            instance_list_file = os.path.join(run_dir, "instances")
            with open( instance_list_file, 'a' ) as f:
                print( self.instance_id, file=f )

        pid_file = os.path.join(instance_dir, "pid")
        err_file = os.path.join(instance_dir, "err.log")
        out_file = os.path.join(instance_dir, "out.log")
        exit_file = os.path.join(instance_dir, "exit")
        proc_file = os.path.join(instance_dir, "proc.json")
        now = datetime.datetime.utcnow().isoformat() + 'Z'

        cmd = self.entry + "; echo $? > " + exit_file

        out_stream = None
        err_stream = None

        if not shutil.which('ts'):
            raise Exception("require 'ts' from 'moreutils' package for time-stamping logs")

        if self.entry[0:5] == "sudo ":
            # pre-populate sudo cache
            subprocess.run(['sudo', 'echo', 'Authorized'], check=True)

        with open( pid_file, 'w' ) as f:
            # logger / log-rotator
            if shutil.which('multilog'):
                # FIXME multilog might not be able to open those files if a previous instance is still terminating
                out_stream = subprocess.Popen(['multilog','t','n100','s16777215',out_file+'.d'],
                        stdin=subprocess.PIPE).stdin
                err_stream = subprocess.Popen(['multilog','t','n100','s16777215',err_file+'.d'],
                        stdin=subprocess.PIPE).stdin
            else:
                # no rotation ...
                out_stream = subprocess.Popen('ts "%FT%H:%M:%.SZ" >> {}'.format(out_file),
                        shell=True,
                        stdin=subprocess.PIPE).stdin
                err_stream = subprocess.Popen('ts "%FT%H:%M:%.SZ" >> {}'.format(err_file),
                        shell=True,
                        stdin=subprocess.PIPE).stdin

            # actual process spawn
            process = subprocess.Popen(cmd, cwd=w_dir, shell=True, stdout=out_stream, stderr=err_stream)
            f.write(str(process.pid))
            with open( proc_file, 'w' ) as pf:
                print( json.dumps({
                    'tag':self.tag,
                    'cwd':w_dir,
                    'cmd':cmd,
                    'entry':self.entry,
                    'started':now
                    }), file=pf )
            return process.pid
