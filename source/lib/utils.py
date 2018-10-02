"""
Generic shared utilities
"""

from itertools import ifilter
import logging
import os
import random
import re
import readline
import shlex
import socket
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
    cron = CronTab('root')
    if remove:
        print_cmd('Removing Akroma MasterNode auto-update...')
        cron.remove_all(comment='Akroma MasterNode Auto-Update')
        cron.write()
    elif not sum(1 for _ in cron.find_comment('Akroma MasterNode Auto-Update')):
        res = input_bool('Auto-update Akroma MasterNode? [Y/n]', 'Y')
        if res == 'Y':
            print_cmd('Enabling Akroma MasterNode auto-update...')
            job = cron.new(command='/usr/sbin/akroma-mn-setup', comment='Akroma MasterNode Auto-Update')
            job.setall('%d %d * * *' % (random.randint(0, 59), random.randint(0, 23)))
            cron.write()
            print_cmd('Enabling and starting cron service...')
            if os_family == 'RedHat':
                ret, _ = timed_run('/usr/bin/yum -d1 -y install cronie')
            else:
                ret, _ = timed_run('/usr/bin/apt-get install cron -y')
            if ret is None or int(ret) != 0:
                raise Exception("ERROR: Failed to install cron")
            service = 'cron' if os_family != 'RedHat' else 'crond'
            for status in ('enable', 'start'):
                service_status(service, status)

def check_perms(filename, permissions, uid=0, gid=0):
    """
    Check and set filename ownership and permissions
    """
    try:
        stat = os.stat(filename)
        mode = oct(stat.st_mode & 0o777)
        if mode != permissions or stat.st_uid != uid or stat.st_gid != gid:
            os.chmod(filename, int(permissions, 8))
            os.chown(filename, uid, gid)
    except OSError:
        raise Exception("ERROR: Failed to set ownership/permissions on %s" % filename)

def check_socket(ip, port, timeout=5):
    """
    Check if an network IP/port socket is open
    Return True if it's open, False otherwise.
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        if not isinstance(port, (int)):
            raise socket.error
        ret = sock.connect((ip, port))
        return True
    except socket.error:
        return False

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

def get_enodeid(args):
    """
    Get enodeid of running geth process
    """
    try:
        user_home = os.path.expanduser('~%s' % args.user)
        ret, out, _ = timed_run('/usr/sbin/geth-akroma attach --datadir %s/.akroma/ --exec "admin.nodeInfo.id"' % user_home, separate_stderr=True)
        if ret is None or int(ret) != 0:
            raise ValueError
    except ValueError:
        return 'ERROR: Failed to read enode id'
    return re.sub(r'"', '', out.rstrip())

def input_bool(text, default):
    """
    Accept input from CLI until Y, N, or CTRL-C pressed
    """
    try:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        tty.setraw(sys.stdin.fileno())
        sys.stdout.write('%s ' % text)
        res = ''
        while res not in ('Y', 'N'):
            res = sys.stdin.read(1).upper()
            if res == "\x03":
                raise KeyboardInterrupt
            if res == '\r':
                res = default
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    print res
    return res

def input_text(text, default=''):
    """
    Accept any input from CLI
    """
    default = str(default) if isinstance(default, (int)) else default
    readline.set_startup_hook(lambda: readline.insert_text(default))
    try:
        return raw_input('%s ' % text)
    finally:
        readline.set_startup_hook()

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

def my_ip():
    """
    Get public ip address of server
    TODO: Refactor into using requests/urllib3 AF_INET (not AF_INET6)
    """
    ret, out = timed_run('/usr/bin/curl --silent -4 icanhazip.com')
    if ret is None or int(ret) != 0:
        return 'ERROR: Failed to obtain node ip'
    return out

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
    # Set default args if undefined
    for i in ('rpcpassword', 'rpcport', 'port', 'rpcuser', 'user'):
        if i not in args:
            setattr(args, i, None)
    for i in ('no_rpcuser', ):
        if i not in args:
            setattr(args, i, False)

    service_file = '/etc/systemd/system/akromanode.service'
    content = None
    try:
        with open(service_file) as fd:
            content = fd.read()
            m = re.search(r'User=(.+)', content)
            if m:
                if args.user is None:
                    args.user = m.group(1)
            m = re.search(r'--port\s+(\d+)', content)
            if m:
                if args.port is None:
                    args.port = int(m.group(1))
            m = re.search(r'--rpcport\s+(\d+)', content)
            if m:
                if args.rpcport is None:
                    args.rpcport = int(m.group(1))
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

    if args.port is None:
        args.port = 30303
    if args.rpcport is None:
        args.rpcport = 8545
    if args.user is None and not os.path.isfile(service_file):
        args.user = 'akroma'
    if args.no_rpcuser:
        args.rpcuser = None
        args.rpcpassword = None
    return content

def print_cmd(cmd):
    """
    Print str surrounded by = signs
    """
    print "=========================="
    print cmd
    print "=========================="

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

def service_status(service, status):
    """
    Check/change provided service status
    """
    ret, _ = timed_run('/bin/systemctl %s %s' % (status, service))
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
