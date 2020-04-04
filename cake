#!/usr/bin/env python3

import time
import sys
import cake
import os
import datetime
import argparse

from logs.watch import LogFilter

def get_args():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("action", default="state", help="action to be taken", choices=["state", "start", "stop", "restart", "logs", "ps"])
    parser.add_argument("-t", "--tag", help="tag of the service / command")
    parser.add_argument("-i", "--instance", help="instance-id of the service / command")
    parser.add_argument("-a", "--all", help="flag for action 'stop' to stop all instances", action="store_true")
    #parser.add_argument("tag", help="command/service tag, can also be provided via --tag", nargs='?')

    try:
        raw_arg_idx = sys.argv.index("-")
    except ValueError as e:
        args = parser.parse_args()
        setattr(args, "raw_args", None)
        return args

    raw_args = sys.argv[raw_arg_idx+1:]
    options = sys.argv[1:raw_arg_idx]
    args = parser.parse_args(options)
    setattr(args, "raw_args", raw_args)
    return args


def get_tags_from_args( args, conf ):
    if args.tag:
        if args.tag not in conf:
            print( "Error: unknown tag", args.tag )
            return []
        return [args.tag]
    return []

def get_tags( args, conf ):
    tags = get_tags_from_args( args, conf )
    if tags:
        return tags
    return list(conf.keys())


def state( args ):
    for tag in cake.ConfigProvider.get_config():
        service = cake.Service(tag=tag)
        if not service.is_running():
            print(tag, '- not running')
        else:
            print(tag, '- up')
    print()

    for iid in cake.ConfigProvider.get_instances():
        service = cake.Service(instance_id=iid)
        service.load_config()
        procs = service.get_procs()
        # "$tag ($PID): $cmd ($dir) - $running"
        # datetime.datetime.fromtimestamp(p.create_time()).strftime("%Y-%m-%d %H:%M:%S")
        #print( conf[tag] )
        if procs:
            print( iid )
            print( 'cmd:', service.entry )
            print( 'cwd:', service.cwd )
            print("\n".join([str((p.pid, p.status(), p.create_time(), p.cmdline())) for p in procs]))
            print('')


def stop( args ):
    if args.instance:
        print( cake.Service(instance_id=args.instance).stop() )

    if args.tag:
        print( cake.Service(tag=args.tag).stop() )

    if args.all:
        for iid in cake.ConfigProvider.get_instances():
            service = cake.Service(instance_id=iid)
            if service.get_procs():
                try:
                    print( service.stop() )
                except Exception as e:
                    print("Exception stopping service")
                    print(e)


def start( args ):
    conf = cake.ConfigProvider.get_config()

    if args.raw_args and not tags:
        service = cake.Service()
        service.set_entry(args.raw_args)
        service.start()

        time.sleep(2)

        log_filter = LogFilter()
        stdout_file = service.get_stdout_file()
        stderr_file = service.get_stderr_file()
        log_filter.add_stdout(stdout_file)
        log_filter.add_stderr(stderr_file)
        log_filter.show()

    elif args.tag:
        if args.tag in conf:
            service = cake.Service(tag=args.tag)
            if not service.is_running():
                service.start()
            else:
                print("Service already up")
        else:
            print( "Error: unknown tag", args.tag )


def logs( args, run_dir=cake.Service.DEFAULT_RUN_DIR ):
    log_filter = LogFilter()
    for iid in cake.ConfigProvider.get_instances():
        service = cake.Service(instance_id=iid)
        if args.all or service.is_running():
            stdout_file = service.get_stdout_file()
            stderr_file = service.get_stderr_file()
            log_filter.add_stdout(stdout_file)
            log_filter.add_stderr(stderr_file)

    log_filter.show()


if __name__ == "__main__":
    args = get_args()

    if(args.action == "start"):
        start(args)

    if(args.action == "state" or args.action == "ps"):
        state(args)

    if(args.action == "stop"):
        stop(args)

    if(args.action == "logs"):
        logs(args)

    if(args.action == "restart"):
        stop(args)
        start(args)
