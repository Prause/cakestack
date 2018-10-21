#!/usr/bin/env python3

import cake
import os
import datetime
import argparse

def get_args():
    parser = argparse.ArgumentParser(description="")
    parser.add_argument("action", default="state", help="action to be taken", choices=["state", "start", "stop", "restart", "logs", "ps"])
    parser.add_argument("-t", "--tag", help="tag of the service / command")
    #parser.add_argument("tag", help="command/service tag, can also be provided via --tag", nargs='?')
    return parser.parse_args()

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

def state( args, conf ):
    tags = get_tags( args, conf )
    for tag in tags:
        service = cake.Service(tag)
        procs = service.get_procs()
        # "$tag ($PID): $cmd ($dir) - $running"
        # datetime.datetime.fromtimestamp(p.create_time()).strftime("%Y-%m-%d %H:%M:%S")
        print( tag )
        print( conf[tag] )
        print("\n".join([str((p.pid, p.status(), p.create_time(), p.cmdline())) for p in procs]))
        if procs:
            print('')



def stop( args, conf ):
    tags = get_tags_from_args( args, conf )
    for tag in tags:
        print( cake.Service(tag).stop() )


def start( args, conf ):
    tags = get_tags_from_args( args, conf )

    for tag in tags:
        service = cake.Service(tag)
        if not service.running():
            service.start()


def logs( args, conf, run_dir=cake.Service.DEFAULT_RUN_DIR ):
    tags = get_tags( args, conf )
    for tag in tags:
        out_file = os.path.expandvars( os.path.join(run_dir, tag, "out.log") )
        if os.path.isfile( out_file ):
            with open( out_file ) as f:
                for line in f:
                    print( tag + " out: " + line.strip() )

        err_file = os.path.expandvars( os.path.join(run_dir, tag, "err.log") )
        if os.path.isfile( err_file ):
            with open( err_file ) as f:
                for line in f:
                    print( tag + " err: " + line.strip() )

if __name__ == "__main__":
    args = get_args()
    conf = cake.Service.read_config()

    if(args.action == "start"):
        start(args, conf)

    if(args.action == "state" or args.action == "ps"):
        state(args, conf)

    if(args.action == "stop"):
        stop(args, conf)

    if(args.action == "logs"):
        logs(args, conf)

    if(args.action == "restart"):
        stop(args,conf)
        start(args,conf)
