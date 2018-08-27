#!/usr/bin/env python
"""Akroma MasterNode Setup and Auto-Update"""

import argparse
import os
import pwd
import sys
import lib.api as api
import lib.utils as utils

GETH_URI = 'https://github.com/akroma-project/akroma/releases/download'
GETH_VERSIONS_URI = 'https://raw.githubusercontent.com/akroma-project/akroma/master/versions.json'
SCRIPTS_URI = 'https://github.com/akroma-project/akroma-masternode-management/releases/download/'
SCRIPTS_VERSIONS_URI = 'https://raw.githubusercontent.com/akroma-project/akroma-masternode-management/master/versions.json'
VERSION = '0.0.4'

# OS and Version compatibility matrix (Major version)
COMPAT_MATRIX = {'CentOS': [7],
                 'Debian': [9],
                 'Ubuntu': [16, 18],
                }

class NegateAction(argparse.Action):
    """
    Allow [--no]-arg toggle
    """
    def __call__(self, parser, ns, values, option):
        setattr(ns, self.dest, option[2:4] != 'no')

def main():
    """Main"""
    parser = argparse.ArgumentParser()
    parser.add_argument("-i", "--interactive", help="Interactively install/upgrade akromanode (Default: False)", \
                        action='store_true')
    parser.add_argument("-g", "--geth", help="Geth version to use (Default: stable)", type=str, \
                        choices=['latest', 'stable'], default=None)
    parser.add_argument("-m", "--memory", "--no-memory", help="Use alternate memory allocator (Default: False)", \
                        dest='memory', nargs=0, action=NegateAction, default=None)
    parser.add_argument("-r", "--remove", help="Uninstall akromanode (Default: False)", action='store_true')
    parser.add_argument("-p", "--rpcport", help="RPC Port (Default: 8545)", type=int, default=None)
    parser.add_argument("--port", help="Network listening port (Default: 30303)", type=int, default=None)
    parser.add_argument("-u", "--user", help="Run akromanode as non-root user (Default: akroma)", nargs='?', \
                        const='akroma', type=str, default=None)
    parser.add_argument("--rpcuser", help="RPC User (Optional)", type=str)
    parser.add_argument("--rpcpassword", help="RPC Password (Optional)", type=str)
    parser.add_argument("--no-rpcuser", help="Remove RPC User/Password (Optional)", action='store_true')
    parser.add_argument("--no-rpcpassword", help="Remove RPC User/Password (Optional)", dest="no_rpcuser", \
                        action='store_true')
    parser.add_argument("--ufw", help="Configure UFW (Optional)", action='store_true')
    parser.add_argument("-v", "--version", help="Script Version", action='store_true')
    args = parser.parse_args()

    # Display script version
    if args.version:
        print "Version: %s" % VERSION
        sys.exit(0)

    # Get the OS, OS family (ie, Debian or RedHat),  OS version, and machine architecture
    os_name, os_family, os_ver, os_arch = utils.os_detect()
    if os_name not in COMPAT_MATRIX or os_ver not in COMPAT_MATRIX[os_name]:
        print "Unsupported OS and/or version.  Please refer to installation guide for supported OS and version"
        sys.exit(2)

    # Migrate old masternode service to akromanode
    restart_service = False
    if utils.service_status('masternode', 'is-active'):
        utils.print_cmd('Migrating masternode service...')
        if utils.service_status('masternode', 'stop'):
            os.rename('/etc/systemd/system/masternode.service', '/etc/systemd/system/akromanode.service')
            ret, _ = utils.timed_run('systemctl daemon-reload')
            if ret is None or int(ret) != 0:
                raise Exception('ERROR: Migration of masternode service failed')
            restart_service = True
        else:
            raise Exception('ERROR: Failed to stop masternode service')

    # Remove Akroma MasterNode
    if args.interactive:
        res = utils.input_bool('Remove masternode installation [y|N]', 'N')
        args.remove = True if res == 'Y' else False
    if args.remove:
        print "Removing masternode installation..."
        f = '/etc/systemd/system/akromanode.service'
        if os.path.isfile(f):
            for status in ('stop', 'disable'):
                if not utils.service_status('akromanode', status):
                    raise Exception("ERROR: Failed to %s akromanode service" % status)
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

    # Get current geth version, and those returned by API
    geth_versions = api.get_script_versions(GETH_VERSIONS_URI, '/usr/sbin/geth-akroma version')
    service_file = utils.parse_service_file(args) # Parse akromanode.service, if it exists, and override defaults
    new_service_file = """[Unit]
Description=Akroma Client -- masternode service
After=network.target

[Service]
"""

    # Gather data for interactive mode
    if args.interactive:
        # User
        while True:
            args.user = 'root' if args.user is None else args.user
            res = utils.input_text('Run akromanode as non-root user (Default: akroma):', args.user)
            res = None if res.isspace() or res == '' else res
            if res is None or (res and utils.isvalidusername(res)):
                args.user = res if res != 'root' else res
                break
            else:
                print "Please provide valid username."
        # Network Listening Port
        while True:
            res = utils.input_text('Network listening port (Default: 30303):', args.port)
            res = 30303 if res.isspace() or res == '' else res
            if isinstance(res, (int)) or res.isdigit():
                args.port = int(res)
                break
            else:
                print "Invalid Network listening Port"
        # RPC Port
        while True:
            res = utils.input_text('RPC Port (Default: 8545):', args.rpcport)
            res = 8545 if res.isspace() or res == '' else res
            if isinstance(res, (int)) or res.isdigit():
                args.rpcport = int(res)
                break
            else:
                print "Invalid RPC Port"
        # Remove RPC User/Password
        if args.rpcuser or args.rpcpassword:
            res = utils.input_bool('Remove RPC User/Password [y|N]', 'N')
            if res == 'Y':
                args.no_rpcuser = True
                args.no_rpcpassword = True
                args.rpcuser = None
                args.rpcpassword = None
        if not args.no_rpcuser:
            # RPC User
            while True:
                res = utils.input_text('RPC User (Optional):', args.rpcuser)
                res = None if res.isspace() or res == '' else res
                if res is None or (res and utils.isvalidrpcinfo(res)):
                    args.rpcuser = res
                    break
                else:
                    print "Invalid RPC User"
            # RPC Password
            while True:
                res = utils.input_text('RPC Password (Optional):', args.rpcpassword)
                res = None if res.isspace() or res == '' else res
                if res is None or (res and utils.isvalidrpcinfo(res)):
                    args.rpcpassword = res
                    break
                else:
                    print "Invalid RPC Password"

    # Ensure all appropriate arguments have been set
    if (args.rpcuser and args.rpcpassword is None) or (args.rpcuser is None and args.rpcpassword):
        parser.error("--rpcuser requires --rpcpassword.")

    if (args.rpcuser and not utils.isvalidrpcinfo(args.rpcuser)) or \
       (args.rpcpassword and not utils.isvalidrpcinfo(args.rpcpassword)):
        parser.error("Please provide valid rpcuser/password.")

    if args.user is not None and not utils.isvalidusername(args.user):
        parser.error("Please provide valid username.")

    # Create/verify user to run akromanode exists
    if args.user:
        new_service_file += "User={0}\nGroup={0}\n".format(args.user)
        utils.print_cmd('User configuration.')
        try:
            pwd.getpwnam(args.user)
            print "User %s found." % args.user
        except KeyError:
            print "Creating user %s." % args.user
            if os_family == 'RedHat':
                ret, _ = utils.timed_run('adduser -r %s -s /bin/false -b /home -m' % args.user)
            else:
                ret, _ = utils.timed_run('adduser %s --gecos "" --disabled-password --system --group' % args.user)
            if ret is None or int(ret) != 0:
                raise Exception("ERROR: Failed to create user %s" % args.user)

    new_service_file += "Type=simple\nRestart=always\nRestartSec=30s\n"

    # Install OS Family specific dependencies
    utils.print_cmd('Installing dependencies...')
    if os_family == 'RedHat':
        ret, _ = utils.timed_run('yum -d1 -y install curl')
    else:
        ret, _ = utils.timed_run('apt-get install curl -y')
    if ret is None or int(ret) != 0:
        raise Exception("ERROR: Failed to install curl")

    # Install alternate memory manager, if True
    if args.interactive:
        res = utils.input_bool('Use alternative memory manager [y|N]', 'N')
        args.memory = True if res == 'Y' else False
    if args.memory:
        if os_arch == 'x86_64':
            utils.print_cmd('Installing jemalloc...')
            if os_family == 'RedHat':
                new_service_file += 'Environment="LD_PRELOAD=/usr/lib64/libjemalloc.so.1"\n'
                ret, _ = utils.timed_run('yum -d1 -y install jemalloc')
            else:
                new_service_file += 'Environment="LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libjemalloc.so.1"\n'
                ret, _ = utils.timed_run('apt-get install libjemalloc1 -y')
            if ret is None or int(ret) != 0:
                raise Exception("ERROR: Failed to install jemalloc")
        else:
            print "Alternate memory manager is only compatible on 64-bit architectures"

    # Install and configure UFW, if True
    if args.interactive:
        res = utils.input_bool('Install and configure ufw [y|N]', 'N')
        args.ufw = True if res == 'Y' else False
    if args.ufw:
        if os_arch == 'x86_64' or os_family == 'Debian':
            ufw_rules = ['ufw --force reset',
                         'ufw --force disable',
                         'ufw default deny incoming',
                         'ufw default allow outgoing',
                         'ufw allow ssh',
                         'ufw allow %s/tcp' % args.rpcport,
                         'ufw allow %s/tcp' % args.port,
                         'ufw allow %s/udp' % args.port,
                         'ufw --force enable',
                         'ufw status'
                        ]
            utils.print_cmd('Installing/configuring ufw...')
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
            for status in ('enable', 'start'):
                utils.service_status('ufw', status)
        else:
            print "ufw is only compatible with 64-bit architectures or Debian based OS'"

    # Determine if geth version needs to be updated
    if geth_versions['current'] == 'Unknown' or geth_versions['current'] < geth_versions['stable']:
        if args.geth is None:
            args.geth = 'stable'
    elif geth_versions['current'] > geth_versions['stable'] and geth_versions['current'] != geth_versions['latest']:
        if args.geth is None:
            args.geth = 'latest'

    # Swap geth from stable <-> latest
    if args.interactive:
        while True:
            res = utils.input_text('Geth version to use (Default: stable):', args.geth)
            res = None if res.isspace() or res == '' else res
            if res is None or res in ('stable', 'latest'):
                args.geth = res
                break
            else:
                print "Geth version must be stable or latest"

    # If geth version update required, download and install new version
    if args.geth:
        utils.print_cmd('Installing/upgrading geth %s...' % geth_versions[args.geth])
        if not api.download_geth(os_arch, geth_versions[args.geth], GETH_URI):
            raise Exception('ERROR: Failed to download geth')
        restart_service = True

    new_service_file += "ExecStart=/usr/sbin/geth-akroma --masternode"

    if args.port != 30303:
        new_service_file += " --port {0}".format(args.port)

    new_service_file += " --rpcport {0} --rpcvhosts *".format(args.rpcport)

    if args.rpcuser:
        new_service_file += " --rpcuser {0} --rpcpassword {1}".format(args.rpcuser, args.rpcpassword)

    new_service_file += "\n\n[Install]\nWantedBy=default.target\n"

    # If auto-generated service file != on-disk service file, rewrite it
    if service_file != new_service_file:
        utils.print_cmd('Creating/updating akromanode service file...')
        f = '/etc/systemd/system/akromanode.service'
        with open(f, 'w') as fd:
            fd.write(new_service_file)
            utils.check_perms(f, '0644')
        ret, _ = utils.timed_run('systemctl daemon-reload')
        if ret is None or int(ret) != 0:
            raise Exception('ERROR: Failed to reload systemctl')
        restart_service = True

    # Enable and restart akromanode if service or geth updates have been made
    if not utils.service_status('akromanode', 'is-active') or restart_service:
        utils.print_cmd('Enabling and (re)starting akromanode service...')
        for status in ('enable', 'restart'):
            utils.service_status('akromanode', status)

    # Enable auto-update and update scripts
    # Get current setup version, and those returned by API
    script_versions = api.get_script_versions(SCRIPTS_VERSIONS_URI, 'akroma-mn-setup -v')
    if script_versions['current'] != script_versions['stable']:
        api.autoupdate_scripts(os_arch, script_versions['stable'], SCRIPTS_URI)
    utils.autoupdate_cron(os_family)

    utils.print_cmd('Akroma MasterNode up-to-date...')

if __name__ == '__main__':
    main()
