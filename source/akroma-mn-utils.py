#!/usr/bin/env python
"""Akroma MasterNode Utils"""

import argparse
import os
import re
import socket
import sys
from lib.api import get_script_versions
from lib.utils import parse_service_file, service_status, timed_run

GETH_VERSIONS_URI = 'https://raw.githubusercontent.com/akroma-project/akroma/master/versions.json'
VERSION = '0.0.4'

def main():
    """Main"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", help="Script Version", action='store_true')
    args = parser.parse_args()

    # Display script version
    if args.version:
        print "Version: %s" % VERSION
        sys.exit(0)

    parse_service_file(args) # Parse akromanode.service
    if args.user is None:
        args.user = 'root'

    # Determine if akromanode service is running
    systemd_inuse = service_status('akromanode', 'is-active')

    # Get akromanode enode id
    user_home = os.path.expanduser('~%s' % args.user)
    ret, out = timed_run('/usr/sbin/geth-akroma attach --datadir %s/.akroma/ --exec "admin.nodeInfo.id"' % user_home)
    if ret is None or int(ret) != 0:
        raise Exception("ERROR: Failed to read enode id")
    enode_id = re.sub(r'"', '', out)

    # Get public ip
    ret, out = timed_run('curl --silent -4 icanhazip.com')
    if ret is None or int(ret) != 0:
        raise Exception("ERROR: Failed to obtain node ip")
    else:
        node_ip = str(out)

    # Get geth versions
    geth_versions = get_script_versions(GETH_VERSIONS_URI, '/usr/sbin/geth-akroma version')

    # Check if node port is accessible
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        if not isinstance(args.rpcport, (int)):
            raise socket.error
        ret = sock.connect((node_ip, args.rpcport))
        node_port_accessible = True
    except socket.error:
        node_port_accessible = False

    # Get akromanode debug journal data
    if systemd_inuse:
        ret, out = timed_run('journalctl -u akromanode.service -n 20 -p 5')
        if ret is None or int(ret) != 0:
            print "ERROR: Failed to read akromanode journal data"
        else:
            journal_data = str(out)

    print "Enode Id: %s" % enode_id
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
        print journal_data

if __name__ == '__main__':
    main()
