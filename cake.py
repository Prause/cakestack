#!/usr/bin/env python3

import os
import datetime
import signal
import psutil
import yaml
import subprocess

DEFAULT_RUN_DIR='$HOME/.cakestack/run'
CAKESTACK_DIR='$HOME/.cakestack'

def check_and_create_dir( dst ):
    if os.path.isfile( dst ):
        print( "Error: dir already exists and is a file", dst )
        return False
    if not os.path.isdir( dst ):
        print( "creating dir", dst )
        os.makedirs( dst )
    return True

def start_command(tag, command, working_dir=None, run_dir=DEFAULT_RUN_DIR):
    print( "starting...", tag )

    tag_run_dir = os.path.abspath( os.path.expandvars( os.path.join( run_dir, tag ) ) )
    if not check_and_create_dir( tag_run_dir ):
        print("Error: Failed creating run dir!", tag_run_dir)
        return

    w_dir = tag_run_dir if not working_dir else os.path.expandvars(working_dir)

    with open( os.path.join(tag_run_dir, "pid"), 'w' ) as f:
        err_file = os.path.join(tag_run_dir, "err.log")
        out_file = os.path.join(tag_run_dir, "out.log")
        exit_file = os.path.join(tag_run_dir, "exit")
        f_err = open( err_file, 'a' )
        f_out = open( out_file, 'a' )
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        print( "starting at " + now, file=f_out )
        print( "starting at " + now, file=f_err )
        cmd = command + "; echo $? > " + exit_file
        process = subprocess.Popen(cmd, cwd=w_dir, shell=True, stdout=f_out, stderr=f_err)
        f.write(str(process.pid))
    return process.pid

def read_config():
    conf_file = os.path.expandvars( os.path.join( CAKESTACK_DIR, "config.yaml"))
    if not os.path.isfile( conf_file ):
        print("Config file not found", conf_file)
        return {}
    with open( conf_file ) as f:
        return yaml.load( f.read() )

def get_procs( tag, run_dir=DEFAULT_RUN_DIR ):
    pid_file = os.path.expandvars( os.path.join( run_dir, tag, "pid" ) )
    if not os.path.isfile( pid_file ):
        print( "No pid file found for", tag )
        return []

    with open( pid_file ) as f:
        pid = int( f.read() )
        try:
            parent = psutil.Process(pid)
            children = parent.children(recursive=True)
            children += [parent]
            return children
        except psutil.NoSuchProcess:
            print( "No process found for", tag )
            return []

def stop_tag( tag, conf ):
    procs = get_procs( tag )
    for p in procs:
        p.send_signal(signal.SIGTERM)
    return psutil.wait_procs(procs, timeout=1)

def start_tag( tag, conf ):
    if "entry" not in conf[tag]:
        print( "No entry point defined:", tag )
        return

    if "dir" in conf[tag]:
        start_command(tag, conf[tag]["entry"], working_dir=conf[tag].get("dir"))

    elif "git" in conf[tag]:
        repo_dir = os.path.expandvars( os.path.join(DEFAULT_RUN_DIR, tag, 'repo') )
        latest_file = os.path.join( repo_dir, 'latest' )
        if not os.path.isfile(latest_file):
            print( "No latest commit hash found, skipping:", tag )
            return

        with open( latest_file ) as f:
            commit_hash = f.readline().strip()
            w_dir = os.path.join( repo_dir, commit_hash )
            if os.path.isdir(w_dir):
                start_command(tag, conf[tag]["entry"], working_dir=w_dir)
            else:
                print( "No commit dir found, skipping:", tag )

    else:
        start_command(tag, conf[tag]["entry"])

