========================
Team and repository tags
========================
.. https://github.com/akroma-project/akroma-masternode-management


Features
--------

* TODO

1. utils.check_perms check inside main loop
2. utils.check_perms to check/change permissions only if exists
3. Refactor __main__ (mostly done)
4. Introduce rpcnode templates for service file and nginx
5. Add fail2ban option
6. Drop curl dependency and perform AF_INET request/urllib3
7. Check akroma-mn-utils version as well to see if it's out-of-date

Howto
-----

1. Install OS dependencies::

   CentOS/RHEL requires the following to be installed prior to running:

    yum install epel-release
    yum install gcc python2-dateutil python2-devel python2-distro python2-future python-jinja2 python2-pip python-retrying python-setuptools upx


2. Install python requirements::

    pip install -r requirements.txt

2. Compile architecture specific binaries, in dist/ folder::

    pyinstaller --clean akroma-mn-setup.spec
    pyinstaller --clean akroma-mn-utils.spec

3. Submit new binaries to GH repo renamed as akroma-mn-setup.`uname -m` and akroma-mn-utils.`uname -m`
   Binaries will initially be named dist/akroma-mn-setup and dist/akroma-mn-utils

   For 32-bit, you may need to manually download pip from https://pypi.org/project/pip/
   Also, upx may not be available for all 32-bit OS', causing binaries to be uncompressed

Known Issues
------------

1. When executing compiled script, you receive::

    "error while loading shared libraries: libz.so.1: failed to map segment from shared object: Operation not permitted"

   This is due to the OS TMPDIR being mounted noexec.  Issue 'mount -o remount,exec /dev/shm', and you may need to update
   /etc/fstab.  In the future, you'll be able to issue something like this::

    TMPDIR='<path where you can execute scripts>' ./scriptname

   For example::

    TMPDIR=/dev/shm ./akroma-mn-setup

   For now, we're setting the tmpdir from pyinstaller with "--runtime-tmpdir /dev/shm".  If this causes issues on some arches,
   we'll need to note it here.

2. When running pyinstaller, you may receive "WARNING: library user32 required via ctypes not found".  This can be ignored.

3. To ensure as wide-spread universal support for 32 and 64-bit, build the binaries on CentOS 7.x, minimal setup.
