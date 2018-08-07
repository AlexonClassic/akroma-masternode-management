#!/usr/bin/env python
"""Akroma MasterNode Utils"""

import argparse
import re
import socket
import sys
from lib.api import get_script_versions
from lib.utils import service_status, timed_run

GETH_VERSIONS_URI = 'https://raw.githubusercontent.com/akroma-project/akroma/master/versions.json'
VERSION = '0.0.3'

def main():
    """Main"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", help="Script Version", action='store_true')
    args = parser.parse_args()

    # Display script version
    if args.version:
        print "Version: %s" % VERSION
        sys.exit(0)

    # Determine if akromanode service is running
    systemd_inuse = service_status('akromanode', 'is-active')

    # Get akromanode enode id and node port
    enode_id = 'Unknown'
    node_port = 'Unknown'
    if systemd_inuse:
        ret, out = timed_run('journalctl -u akromanode.service')
        if ret is None or int(ret) != 0:
            raise Exception("ERROR: Failed to read akromanode journal data")
        m = re.search(r'HTTP endpoint opened\s*url=http:\/\/0.0.0.0:(\d+)\s*', out)
        if m:
            node_port = int(m.group(1))
        m = re.search(r'UDP listener up\s*self=enode:\/\/(\w+)\@', out)
        if m:
            enode_id = str(m.group(1))

    # Get public ip
    ret, out = timed_run('curl --silent -4 icanhazip.com')
    if ret is None or int(ret) != 0:
        raise Exception("ERROR: Failed to obtain node ip")
    else:
        node_ip = str(out)

    # Get geth versions
    geth_versions = get_script_versions(GETH_VERSIONS_URI, 'geth version')

    # Check if node port is accessible
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        if not isinstance(node_port, (int)):
            raise socket.error
        ret = sock.connect((node_ip, node_port))
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
    if enode_id == 'Unknown':
        print "\tConsider issuing `systemctl restart akromanode` and re-running utils"
    print "Node IP: %s" % node_ip
    print "Node Port: %s" % node_port
    if node_ip == 'Unknown':
        print "\tConsider issuing `systemctl restart akromanode` and re-running utils"
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
