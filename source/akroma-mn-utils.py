#!/usr/bin/env python
# Akroma MasterNode Utils

import argparse
import re
import socket
import sys
from lib.api import get_script_versions
from lib.utils import service_status, timed_run

GETH_VERSIONS_URI = 'https://raw.githubusercontent.com/akroma-project/akroma/master/versions.json'
VERSION = '0.0.2'

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--version", help="Script Version", action='store_true')
    args = parser.parse_args()

    # Display script version
    if args.version:
        print("Version: %s" % VERSION)
        sys.exit(0)

    # Determine if akromanode service is running
    SYSTEMD_INUSE = service_status('akromanode', 'is-active')

    # Get akromanode enode id and node port
    ENODE_ID = 'Unknown'
    NODE_PORT = 'Unknown'
    if SYSTEMD_INUSE:
        ret, out = timed_run('journalctl -u akromanode.service')
        if ret is None or int(ret) != 0:
            raise Exception("ERROR: Failed to read akromanode journal data")
    else:
        with open('geth.out', 'r') as f:
            out = f.read().rstrip()
    m = re.search(r'HTTP endpoint opened\s*url=http:\/\/0.0.0.0:(\d+)\s*', out)
    if m:
        NODE_PORT = int(m.group(1))
    m = re.search(r'UDP listener up\s*self=enode:\/\/(\w+)\@', out)
    if m:
        ENODE_ID = str(m.group(1))

    # Get public ip
    ret, out = timed_run('curl --silent -4 icanhazip.com')
    if ret is None or int(ret) != 0:
        raise Exception("ERROR: Failed to obtain node ip")
    else:
        NODE_IP = str(out)

    # Get geth versions
    geth_versions = get_script_versions(GETH_VERSIONS_URI, 'geth version')

    # Check if node port is accessible
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        ret = sock.connect((NODE_IP, NODE_PORT))
        NODE_PORT_ACCESSIBLE = True
    except Exception:
        NODE_PORT_ACCESSIBLE = False

    # Get akromanode debug journal data
    if SYSTEMD_INUSE:
        ret, out = timed_run('journalctl -u akromanode.service -n 20 -p 5')
        if ret is None or int(ret) != 0:
            print("ERROR: Failed to read akromanode journal data")
        else:
            JOURNAL_DATA = str(out)

    print("Enode Id: %s" % ENODE_ID)
    if ENODE_ID == 'Unknown':
        print("\tConsider issuing `systemctl restart akromanode` and re-running utils")
    print("Node IP: %s" % NODE_IP)
    print("Node Port: %s" % NODE_PORT)
    if NODE_IP == 'Unknown':
        print("\tConsider issuing `systemctl restart akromanode` and re-running utils")
    print("Geth Versions:")
    for k, v in sorted(geth_versions.items()):
        print("\t%s : %s" % (k, v))
    print("Service Is-Active: %s" % SYSTEMD_INUSE)
    print("Port is open locally: %s" % NODE_PORT_ACCESSIBLE)
    if SYSTEMD_INUSE:
        print("Service Error(s):")
        print(JOURNAL_DATA)

if __name__ == '__main__':
    main()
