#!/usr/bin/env python
"""Akroma MasterNode Utils"""

import argparse
import os
import sys
from lib.api import get_script_versions
import lib.utils as utils

GETH_VERSIONS_URI = 'https://raw.githubusercontent.com/akroma-project/akroma/master/versions.json'
VERSION = '0.0.7'

def main():
    """Main"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", help="Script Version", action='store_true')
    args = parser.parse_args()

    # Display script version
    if args.version:
        print "Version: %s" % VERSION
        sys.exit(0)

    utils.parse_service_file(args) # Parse akromanode.service
    if args.user is None:
        args.user = 'root'

    # Get public ip
    node_ip = utils.my_ip()

    # Check if node port is accessible
    node_port_accessible = utils.check_socket(node_ip, args.rpcport)

    # Determine if akromanode service is running
    systemd_inuse = utils.service_status('akromanode', 'is-active')

    # Get geth versions
    geth_versions = get_script_versions(GETH_VERSIONS_URI, '/usr/sbin/geth-akroma version')

    print "Enode Id: %s" % utils.get_enodeid(args)
    print "Node IP: %s" % node_ip
    print "Node Port: %s" % args.rpcport
    if args.rpcuser is not None and args.rpcpassword is not None:
        print "RPC User: %s" % args.rpcuser
        print "RPC Password: %s" % args.rpcpassword
    print "Geth Versions:"
    for k, v in sorted(geth_versions.items()):
        print "\t%s : %s" % (k, v)
    print "Service Is-Active: %s" % systemd_inuse
    print "Port is open locally: %s" % node_port_accessible
    if systemd_inuse:
        print "Service Error(s):"
        ret, out = utils.timed_run('/bin/journalctl -u akromanode.service -n 20 -p 5')
        if ret is None or int(ret) != 0:
            print "ERROR: Failed to read akromanode journal data"
        else:
            print out

if __name__ == '__main__':
    main()
