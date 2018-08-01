#!/usr/bin/env python
# Akroma MasterNode Setup and Auto-Update

import argparse
import os
import pwd
import sys
import lib.api as api
import lib.utils as utils

GETH_URI = 'https://github.com/akroma-project/akroma/releases/download'
GETH_VERSIONS_URI = 'https://raw.githubusercontent.com/akroma-project/akroma/master/versions.json'
SCRIPTS_URI = 'https://github.com/akroma-project/akroma-masternode-management/releases/download/'
SCRIPTS_VERSIONS_URI = 'https://raw.githubusercontent.com/akroma-project/akroma-masternode-management/master/scripts/versions.json'
VERSION = '0.0.1'

class NegateAction(argparse.Action):
    """
    Allow [--no]-arg toggle
    """
    def __call__(self, parser, ns, values, option):
        setattr(ns, self.dest, option[2:4] != 'no')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interactive", help="Interactively install/upgrade akromanode (NOT YET IMPLEMENTED)", action='store_true')
    parser.add_argument("-g", "--geth", help="Geth version to use (Default: stable)", type=str, choices=['latest', 'stable'], default=None)
    parser.add_argument("-m", "--memory", "--no-memory", help="Use alternate memory allocator (Default: False)", dest='memory', nargs=0, action=NegateAction, default=None)
    parser.add_argument("-r", "--remove", help="Uninstall akromanode (Default: False)", action='store_true')
    parser.add_argument("-p", "--rpcport", help="RPC Port (Default: 8545)", type=int, default=None)
    parser.add_argument("-u", "--user", help="Run akromanode as non-root user (Default: akroma)", nargs='?', const='akroma', type=str, default=None)
    parser.add_argument("--rpcuser", help="RPC User (Optional)", type=str)
    parser.add_argument("--rpcpassword", help="RPC Password (Optional)", type=str)
    parser.add_argument("--no-rpcuser", help="Remove RPC User/Password (Optional)", action='store_true')
    parser.add_argument("--no-rpcpassword", help="Remove RPC User/Password (Optional)", dest="no_rpcuser", action='store_true')
    parser.add_argument("--ufw", help="Configure UFW (Optional)", action='store_true')
    parser.add_argument("-v", "--version", help="Script Version", action='store_true')
    args = parser.parse_args()

    # Display script version
    if args.version:
        print("Version: %s" % VERSION)
        sys.exit(0)

    os_family, arch = utils.os_detect() # Get the OS family (ie, Debian or RedHat) and machine architecture

    # Remove Akroma MasterNode
    if args.remove:
        print("Removing masternode installation...")
        for service in ('akromanode', 'masternode'):
            f = '/etc/systemd/system/%s.service' % service
            if os.path.isfile(f):
                for status in ('stop', 'disable'):
                    if not utils.service_status(service, status):
                        raise Exception("ERROR: Failed to %s %s service" % (syscall, service))
                # If service file was a symlink, systemctl would have removed it
                # Check if the file still exists
                if os.path.isfile(f):
                    os.remove(f)
        utils.autoupdate_cron(os_family, remove=True)
        # Remove scripts
        for f in ('geth', 'akroma-mn-setup', 'akroma-mn-utils'):
            f = '/usr/sbin/' + f
            if os.path.isfile(f):
                os.remove(f)
        sys.exit(0)

    # Migrate old masternode service to akromanode
    if utils.service_status('masternode', 'is-active'):
        print("==========================\nMigrating masternode service...\n==========================")
        if utils.service_status('masternode', 'stop'):
            os.rename('/etc/systemd/system/masternode.service', '/etc/systemd/system/akromanode.service')
            ret, _ = utils.timed_run('systemctl daemon-reload')
            if ret is None or int(ret) != 0:
                raise Exception('ERROR: Migration of masternode service failed')
        else:
            raise Exception('ERROR: Failed to stop masternode service')

    geth_versions = api.get_script_versions(GETH_VERSIONS_URI, 'geth version') # Get current geth version, and those returned by API
    restart_service = False
    service_file = utils.parse_service_file(args) # Parse akromanode.service, if it exists, and override defaults
    new_service_file = """[Unit]
Description=Akroma Client -- masternode service
After=network.target

[Service]
"""

    # Ensure all appropriate arguments have been set
    if (args.rpcuser and args.rpcpassword is None) or (args.rpcuser is None and args.rpcpassword):
        parser.error("--rpcuser requires --rpcpassword.")

    if (args.rpcuser and not utils.isvalidrpcinfo(args.rpcuser)) or (args.rpcpassword and not utils.isvalidrpcinfo(args.rpcpassword)):
        parser.error("Please provide valid rpcuser/password.")

    if args.user is not None and not utils.isvalidusername(args.user):
        parser.error("Please provide valid username.")

    # Create/verify user to run akromanode exists
    if args.user:
        new_service_file += "User={0}\nGroup={0}\n".format(args.user)
        print("==========================\nUser configuration.\n==========================")
        try:
            pwd.getpwnam(args.user)
            print("User %s found." % args.user)
        except KeyError:
            if os_family in ('Debian', 'RedHat'):
                print("Creating user %s." % args.user)
                if os_family == 'RedHat':
                    ret, _ = utils.timed_run('adduser -r %s -s /bin/false -b /home -m' % args.user)
                else:
                    ret, _ = utils.timed_run('adduser %s --gecos "" --disabled-password --system --group' % args.user)
                if ret is None or int(ret) != 0:
                    raise Exception("ERROR: Failed to create user %s" % args.user)
            else:
                print("Unsupported OS for user management.  Manually create desired user to run akromanode as.")

    new_service_file += "Type=simple\nRestart=always\nRestartSec=30s\n"

    # Install OS Family specific dependencies
    if os_family in ('Debian', 'RedHat'):
        print("==========================\nInstalling dependencies...\n==========================")
        if os_family == 'RedHat':
            ret, _ = utils.timed_run('yum -d1 -y install curl')
        else:
            ret, _ = utils.timed_run('apt-get install curl -y')
        if ret is None or int(ret) != 0:
            raise Exception("ERROR: Failed to install curl")
    else:
        print("Unsupported OS.  Manually install curl package.")

    # Install alternate memory manager, if True
    if args.memory:
        if os_family in ('Debian', 'RedHat'):
            print("==========================\nInstalling jemalloc...\n==========================")
            if os_family == 'RedHat':
                new_service_file += 'Environment="LD_PRELOAD=/usr/lib64/libjemalloc.so.1"\n'
                ret, _ = utils.timed_run('yum -d1 -y install jemalloc')
            else:
                new_service_file += 'Environment="LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.1"\n'
                ret, _ = utils.timed_run('apt-get install libjemalloc1 -y')
            if ret is None or int(ret) != 0:
                raise Exception("ERROR: Failed to install jemalloc")
        else:
            print("Unsupported OS for alternate memory manager.")

    # Install and configure UFW, if True
    if args.ufw:
        if os_family in ('Debian', 'RedHat'):
            ufw_rules = ['ufw --force reset',
                         'ufw --force disable',
                         'ufw default deny incoming',
                         'ufw default allow outgoing',
                         'ufw allow ssh',
                         'ufw allow %s/tcp' % args.rpcport,
                         'ufw allow 30303/tcp',
                         'ufw allow 30303/udp',
                         'ufw --force enable',
                         'ufw status'
                        ]
            print("==========================\nInstalling/configuring ufw...\n==========================")
            if os_family == 'RedHat':
                ret, _ = utils.timed_run('yum -d1 -y install ufw')
            else:
                ret, _ = utils.timed_run('apt-get install ufw -y')
            if ret is None or int(ret) != 0:
                raise Exception("ERROR: Failed to install ufw")
            for rule in ufw_rules:
                ret, _ = utils.timed_run(rule)
                if ret is None or int(ret) != 0:
                    raise Exception("ERROR: Failed to configure ufw")
            utils.service_status('ufw', 'enable')
            utils.service_status('ufw', 'start')
        else:
            print("Unsupported OS for UFW.")

    # Determine if geth version needs to be updated
    if geth_versions['current'] == 'Unknown' or geth_versions['current'] < geth_versions['stable']:
        if args.geth is None:
            args.geth = 'stable'
    elif geth_versions['current'] > geth_versions['stable'] and geth_versions['current'] != geth_versions['latest']:
        if args.geth is None:
            args.geth = 'latest'

    # If geth version update required, download and install new version
    if args.geth:
        print("==========================\nInstalling/upgrading geth %s...\n==========================" % geth_versions[args.geth])
        if not api.download_geth(os_family, arch, geth_versions[args.geth], GETH_URI):
            raise Exception('ERROR: Failed to download geth')
        restart_service = True

    if args.rpcuser:
        new_service_file += "ExecStart=/usr/sbin/geth --masternode --rpcport {0} --rpcvhosts * --rpcuser {1} --rpcpassword {2}\n\n" \
                            .format(args.rpcport, args.rpcuser, args.rpcpassword)
    else:
        new_service_file += "ExecStart=/usr/sbin/geth --masternode --rpcport {0} --rpcvhosts *\n\n".format(args.rpcport)

    new_service_file += "[Install]\nWantedBy=default.target\n"

    # If auto-generated service file != on-disk service file, rewrite it
    if service_file != new_service_file:
        print("==========================\nCreating/updating akromanode service file...\n==========================")
        with open('/etc/systemd/system/akromanode.service', 'w') as fd:
            fd.write(new_service_file)
        ret, _ = utils.timed_run('systemctl daemon-reload')
        if ret is None or int(ret) != 0:
            raise Exception('ERROR: Failed to reload systemctl')
        restart_service = True

    # Enable and restart akromanode if service or geth updates have been made
    if not utils.service_status('akromanode', 'is-active') or restart_service:
        print("==========================\nEnabling and (re)starting akromanode service...\n==========================")
        utils.service_status('akromanode', 'enable')
        utils.service_status('akromanode', 'restart')

    # Enable auto-update and update scripts
    script_versions = api.get_script_versions(SCRIPTS_VERSIONS_URI, 'akroma-mn-setup -v') # Get current setup version, and those returned by API
    if script_versions['current'] != script_versions['stable']:
        api.autoupdate_scripts(arch, script_versions['stable'], SCRIPTS_URI)
    utils.autoupdate_cron(os_family)

    print("==========================\nAkroma MasterNode up-to-date...\n==========================")

if __name__ == '__main__':
    main()
