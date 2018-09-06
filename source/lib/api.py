"""
Interface to interact with requests
"""

import json
import os
import StringIO
import zipfile
import requests
from retrying import retry
import lib.utils as utils

def autoupdate_scripts(arch, version, url):
    """
    Auto-update scripts when new versions detected upstream
    """
    path = '/usr/sbin/'
    url += version + '/'
    for f in ('akroma-mn-setup', 'akroma-mn-utils'):
        ret = HttpRetry().run('GET', url=url + f + '.' + arch)
        if ret.status_code != 200:
            print "ERROR: Failed to update %s" % f
        else:
            f = path + f
            # Need to remove binary before replacing it
            if os.path.isfile(f):
                os.remove(f)
            data = StringIO.StringIO()
            data.write(ret.content)
            data.seek(0)
            with open(f, 'w') as fd:
                utils.print_cmd('Updating %s...' % f)
                fd.write(data.read())
                utils.check_perms(f, '0700')

def download_geth(arch, version, url):
    """
    Download and install geth
    """
    url += '/%s/release.linux-' % version
    if arch == 'x86_64':
        url += 'amd64'
    elif arch == 'armv5l':
        url += 'arm-5'
    elif arch == 'armv6l':
        url += 'arm-6'
    elif arch == 'armv7l':
        url += 'arm-7'
    elif arch == 'armv8l':
        url += 'arm-8'
    elif arch == 'aarch64':
        url += 'arm-64'
    elif arch == 'i686':
        url += '386'
    else:
        print "Unsupported OS for geth.  You may need to setup akromanode manually."
        return False
    url += '.%s.zip' % version

    if utils.service_status('akromanode', 'is-active'):
        utils.service_status('akromanode', 'stop')

    if extract_zip(url, '/usr/sbin'):
        f = '/usr/sbin/geth-akroma'
        utils.check_perms(f, '0755')
        return True
    return False

def extract_zip(url, directory):
    """
    Download zip file, in memory, and extract to disk
    """
    try:
        f = zipfile.ZipFile(StringIO.StringIO(requests.get(url).content))
        for fn in f.infolist():
            if fn.filename == 'geth':
                fn.filename = 'geth-akroma'
            f.extract(fn, directory)
        return True
    except zipfile.BadZipfile:
        return False

def get_script_versions(url, cmd):
    """
    Query scripts versions.json
    """
    headers = {'content-type': 'application/json'}
    ret = HttpRetry().run('GET', \
                  url=url, \
                  headers=headers)

    if ret.status_code != 200:
        raise Exception('"%s" returned error %d' % (url, ret.status_code))

    data = json.loads(ret.content)
    data.update({'current': utils.script_version(cmd)})
    return data

def retry_if_connection_error(exception):
    """
    Retry API connection on error

    Args:
        param1: (obj) Requests exceptions error
    """
    return isinstance(exception, requests.exceptions.ConnectionError)

def do_retry(func, connect_retries, connect_wait_ms, *args, **kwargs):
    """
    API retry decorator

    Args:
        param1: (str) Requests method
        param2: (int) maximum amount to re-connect in case of connection errors
        param3: (int) time between retries on connection error
    """
    @retry(retry_on_exception=retry_if_connection_error, \
           wait_fixed=connect_wait_ms, \
           stop_max_attempt_number=connect_retries)
    def _do_retry(func):
        return func(*args, **kwargs)
    return _do_retry(func)

class HttpRetry(object):
    """
    Class to interact with APIs
    """
    def __init__(self):
        # Supported HTTP methods (mapped to requests' methods)
        self.mapping = {
            'GET': requests.get,
            'POST': requests.post,
            'PUT': requests.put,
            'DELETE': requests.delete,
            'HEAD': requests.head,
            'PATCH': requests.patch,
        }

    def run(self, method, url,\
            params=None, headers=None, \
            timeout=30, connect_retries=10, connect_wait_ms=1000):
        """
        Perform API request

        Args:
            param1: (str) URL
            param2: (dict) Optional parameters to append to URL
            param3: (dict) Optional header override
            param4: (int) maximum timeout to complete the command
            param5: (int) maximum amount to re-connect in case of connection errors
            param6: (int) time between retries on connection error
        """
        try:
            method = self.mapping[method]
        except KeyError:
            raise Exception("Invalid method: %s" % method)
        return do_retry(method, connect_retries, connect_wait_ms, \
                        url, params=params, headers=headers, timeout=timeout)
