"""
Generic shared utilities
"""

from itertools import ifilter
import logging
import os
import random
import re
import shlex
import sys
import termios
import tty
from retrying import retry
from subprocess32 import STDOUT, PIPE, Popen
from crontab import CronTab
import distro


def autoupdate_cron(os_family, remove=False):
    """
    Enable/remove Akroma Auto-update cron
    """
    if os_family in ('Debian', 'RedHat'):
        cron = CronTab('root')
        if remove:
            print "==========================\nRemoving Akroma MasterNode auto-update...\n=========================="
            cron.remove_all(comment='Akroma MasterNode Auto-Update')
            cron.write()
        elif not sum(1 for _ in cron.find_comment('Akroma MasterNode Auto-Update')):
            try:
                fd = sys.stdin.fileno()
                old_settings = termios.tcgetattr(fd)
                tty.setraw(sys.stdin.fileno())
                sys.stdout.write('Auto-update Akroma MasterNode? [Y/n] ')
                res = ''
                while res not in ('Y', 'N'):
                    res = sys.stdin.read(1).upper()
                    if res == "\x03":
                        raise KeyboardInterrupt
                    if res == '\r':
                        res = 'Y'
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            print res
            if res == 'Y':
                print "==========================\nEnabling Akroma MasterNode auto-update...\n=========================="
                job = cron.new(command='/usr/sbin/akroma-mn-setup', comment='Akroma MasterNode Auto-Update')
                job.setall('%d %d * * *' % (random.randint(0, 59), random.randint(0, 23)))
                cron.write()
                print "==========================\nEnabling and starting cron service...\n=========================="
                if os_family == 'RedHat':
                    ret, _ = timed_run('yum -d1 -y install cronie')
                else:
                    ret, _ = timed_run('apt-get install cron -y')
                if ret is None or int(ret) != 0:
                    raise Exception("ERROR: Failed to install cron")
                if os_family == 'RedHat':
                    service_status('crond', 'enable')
                    service_status('crond', 'start')
                else:
                    service_status('cron', 'enable')
                    service_status('cron', 'start')

def execute(cmd, tmo=60, max_retries=1, wait_ms=0, \
            stdin_str=None, log=True, separate_stderr=True):
    """
    Run an external command with a timeout

    Args:
        cmd         : (str) command to execute
        tmo         : (int) maximum timeout to complete an individual execution
                            of the command (in sec)
        max_retries : (int) maximum attempts to run the command if it returns a
                            failure
        wait_ms     : (int) time to wait between a failed attempt and another
                            (in millisec)
        stdin_str   : (str) data passed to stdin of the executed program
        log         : (bool) enable/disable logging
        separate_stderr : (bool) enable/disable separation of stdout and stderr
    """
    @retry(wait_fixed=wait_ms, stop_max_attempt_number=max_retries)
    def _execute(cmd, tmo, stdin_str, log, separate_stderr):
        if log:
            logging.info(">> running '%s' (timeout=%d)" % (cmd, tmo))
        stdin = PIPE if stdin_str is not None else None
        if separate_stderr:
            p = Popen(shlex.split(cmd), stderr=PIPE, stdout=PIPE, stdin=stdin)
            out, err = p.communicate(timeout=tmo, input=stdin_str)
        else:
            p = Popen(shlex.split(cmd), stderr=STDOUT, stdout=PIPE, stdin=stdin)
            out = p.communicate(timeout=tmo, input=stdin_str)[0].rstrip()
            err = ''
        if log:
            logging.info(">>> '%s' returned=%s\nstdout=%s\nstderr=%s" % \
                         (cmd, str(p.returncode), str(out), str(err)))
        if int(p.returncode) != 0:
            raise Exception("%s: returned=%s\nstdout=%s\nstderr=%s" % \
                            (cmd, str(p.returncode), str(out), str(err)))
        if separate_stderr:
            return p.returncode, out, err

        return p.returncode, out
    return _execute(cmd, tmo, stdin_str, log, separate_stderr)

def isvalidusername(user):
    """
    Verify valid username
    """
    if re.match('^[a-zA-Z0-9_-]{2,15}$', user):
        return True
    return False

def isvalidrpcinfo(data):
    """
    Verify valid rpcuser or rpcpassword
    """
    if re.match('^[a-zA-Z0-9]{3,15}$', data):
        return True
    return False

def os_detect():
    """
    Detect os family and architecture
    """
    _os_family_map = {
        'Debian': 'Debian',
        'RedHat': 'Debian',
        'Ubuntu': 'Debian',
        'Fedora': 'RedHat',
        'Chapeau': 'RedHat',
        'Korora': 'RedHat',
        'FedBerry': 'RedHat',
        'CentOS': 'RedHat',
        'GoOSe': 'RedHat',
        'Scientific': 'RedHat',
        'Amazon': 'RedHat',
        'CloudLinux': 'RedHat',
        'OVS': 'RedHat',
        'OEL': 'RedHat',
        'XCP': 'RedHat',
        'XenServer': 'RedHat',
        'RES': 'RedHat',
        'Sangoma': 'RedHat',
        'Mint': 'Debian',
        'ALT': 'RedHat',
        'Trisquel': 'Debian',
        'GCEL': 'Debian',
        'Linaro': 'Debian',
        'elementary OS': 'Debian',
        'ScientificLinux': 'RedHat',
        'Raspbian': 'Debian',
        'Devuan': 'Debian',
        'antiX': 'Debian',
        'Kali': 'Debian',
        'neon': 'Debian',
        'Cumulus': 'Debian',
        'Deepin': 'Debian',
        'KDE neon': 'Debian',
        'IDMS': 'Debian',
    }

    os_name = re.sub(r'\s+(:?GNU/)?Linux$', '', distro.name())
    os_ver = distro.major_version()
    regex = re.compile("^%s$" % os_name, re.IGNORECASE)
    os_family = next(ifilter(regex.match, _os_family_map), False)
    if os_family:
        return os_name, _os_family_map[os_family], int(os_ver), os.uname()[4]
    return os_name, None, int(os_ver), os.uname()[4]

def parse_service_file(args):
    """
    Parse akromanode.service, if it exists, and set/override defaults
    """
    service_file = '/etc/systemd/system/akromanode.service'
    content = None
    try:
        with open(service_file) as fd:
            content = fd.read()
            m = re.search(r'User=(.+)', content)
            if m:
                if args.user is None:
                    args.user = m.group(1)
            m = re.search(r'jemalloc', content)
            if m:
                if args.memory is None:
                    args.memory = True
            m = re.search(r'--rpcport\s+(\d+)', content)
            if m:
                if args.rpcport is None:
                    args.rpcport = m.group(1)
            m = re.search(r'--rpcuser\s+(\w+)', content)
            if m:
                if args.rpcuser is None:
                    args.rpcuser = m.group(1)
            m = re.search(r'--rpcpassword\s+(\w+)', content)
            if m:
                if args.rpcpassword is None:
                    args.rpcpassword = m.group(1)
    except IOError:
        pass

    if args.memory is None:
        args.memory = False
    if args.rpcport is None:
        args.rpcport = 8545
    if args.user is None and not os.path.isfile(service_file):
        args.user = 'akroma'
    if args.no_rpcuser:
        args.rpcuser = None
        args.rpcpassword = None
    return content

def service_status(service, status):
    """
    Check/change provided service status
    """
    ret, _ = timed_run('systemctl %s %s' % (status, service))
    if ret is None or int(ret) != 0:
        return False
    return True

def script_version(cmd):
    """
    Get local script version
    """
    ret, out = timed_run(cmd)
    if ret is None or int(ret) != 0:
        return 'Unknown'
    m = re.search(r'Version:\s*([\.0-9]+)', out)
    if m:
        return str(m.group(1))
    return 'Unknown'

def timed_run(cmd, timeout=120, log=True, stdin_str=None, separate_stderr=False):
    """
    Run an external command with a timeout (handle exceptions internally)
    """
    try:
        ret = execute(cmd, tmo=timeout, log=log,
                      stdin_str=stdin_str, separate_stderr=separate_stderr)
        return [x.rstrip() if isinstance(x, (basestring, str, unicode)) else x for x in ret]
    except Exception:
        return None, None
