import os, subprocess, logging
import socket as socket_module

# Python doesn't expose the `setns()` function manually, so
# we'll use the `ctypes` module to make it available.
from ctypes import CDLL, get_errno

# https://sourceware.org/git/?p=glibc.git;a=blob;f=sysdeps/unix/sysv/linux/bits/sched.h;h=34f27a7d9b9f49d4be826f89234cf0fe45c95c8f;hb=HEAD
CLONE_NEWIPC = 0x08000000
CLONE_NEWNET = 0x40000000
CLONE_NEWUTS = 0x04000000
CLONE_NEWNS  = 0x00020000

# https://sourceware.org/git/?p=glibc.git;a=blob;f=sysdeps/unix/sysv/linux/sys/mount.h;h=ce2838e3a79caf1f49c9aceacb143ff5e403e50e;hb=HEAD
MS_BIND = 4096
MS_REC = 16384
MS_SLAVE = 1 << 19

NETNS_CREATE_SCRIPT = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'create_netns.sh')
NETNS_DESTROY_SCRIPT = os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        'destroy_netns.sh')

logger = logging.getLogger()

def errcheck(ret, func, args):
    if ret == -1:
        e = get_errno()
        raise OSError(e, os.strerror(e))

libc = CDLL('libc.so.6', use_errno=True)
libc.setns.errcheck = errcheck

def mount_resolvconf(path):
    if path is None:
        return
    libc.unshare(CLONE_NEWNS)
    # Make our new mount namespace private
    libc.mount('', '/', '', MS_REC|MS_SLAVE, None)
    libc.mount(path, '/etc/resolv.conf', '', MS_BIND, None)

def unmount_resolvconf():
    libc.umount('/etc/resolv.conf')

def setns(fd, nstype):
    '''Change the network namespace of the calling thread.

    Given a file descriptor referring to a namespace, reassociate the
    calling thread with that namespace.  The fd argument may be either a
    numeric file  descriptor or a Python object with a fileno() method.
    '''

    if hasattr(fd, 'fileno'):
        fd = fd.fileno()

    return libc.setns(fd, nstype)


def socket(nspath, *args):
    '''Return a socket from a network namespace.

    This is a wrapper for socket.socket() that will return a socket
    inside the namespace specified by the nspath argument, which should be
    a filesystem path to an appropriate namespace file.  You can use the
    get_ns_path() function to generate an appropriate filesystem path if
    you know a namespace name or pid.
    '''

    with NetNS(nspath=nspath):
        return socket_module.socket(*args)


def get_ns_path(nspath=None, nsname=None, nspid=None):
    '''Generate a filesystem path from a namespace name or pid.

    Generate a filesystem path from a namespace name or pid, and return
    a filesystem path to the appropriate file.  Returns the nspath argument
    if both nsname and nspid are None.
    '''

    if nsname:
        nspath = '/var/run/netns/%s' % nsname
    elif nspid:
        nspath = '/proc/%d/ns/net' % nspid

    if not os.path.exists(nspath):
        raise ValueError('namespace path %s does not exist' % nspath)

    return nspath

def create_netns():
    completed = subprocess.check_output([NETNS_CREATE_SCRIPT])
    name = completed.decode('utf8').strip()
    logger.info('Created netns: "{}"'.format(name))
    return name

def destroy_netns(name):
    completed = subprocess.check_output([NETNS_DESTROY_SCRIPT, name])
    name = completed.decode('utf8').strip()
    logger.info('Destroyed netns: "{}"'.format(name))
    return name

class NetNS (object):
    '''A context manager for running code inside a network namespace.

    This is a context manager that on enter assigns the current process
    to an alternate network namespace (specified by name, filesystem path,
    or pid) and then re-assigns the process to its original network
    namespace on exit.
    '''

    def __init__(self, nsname=None, nspath=None, nspid=None, resolvconf=None):
        self.nsname = nsname
        self.nspath = nspath
        self.nspid = nspid
        self.resolvconf = resolvconf

        self.my_net_ns = None
        self.my_mnt_ns = None

        self.my_net_path = get_ns_path(nspid=os.getpid())
        self.my_mnt_path = get_ns_path(nspid=os.getpid()).replace('/net', '/mnt')

        self.created_netns = False


    def open(self):
        # If we don't have a namespace we're supposed to enter, create a new
        # one.
        if self.nsname is None and self.nspath is None and self.nspid is None:
            self.nsname = create_netns()
            self.created_netns = self.nsname

        self.target_net_path = get_ns_path(
                nspath=self.nspath,
                nsname=self.nsname,
                nspid=self.nspid)

        if not self.target_net_path:
            raise ValueError('invalid namespace')

        # before entering a new namespace, we open a file descriptor
        # in the current namespace that we will use to restore
        # our namespaces on exit.
        self.my_net_ns = open(self.my_net_path)
        self.my_mnt_ns = open(self.my_mnt_path)

        # https://unix.stackexchange.com/a/443919
        # https://unix.stackexchange.com/a/246468
        if self.resolvconf is None and self.nsname:
            self.resolvconf = '/etc/netns/{}/resolv.conf'.format(self.nsname)
            logger.info('Resolvconf path: {}'.format(self.resolvconf))
        mount_resolvconf(self.resolvconf)

        self.target_net_ns = open(self.target_net_path)
        setns(self.target_net_ns, CLONE_NEWNET)

    def close(self):
        if self.my_net_ns:
            setns(self.my_net_ns, CLONE_NEWNET)
            self.my_net_ns.close()
        if self.my_mnt_ns:
            setns(self.my_mnt_ns, CLONE_NEWNS)
            self.my_mnt_ns.close()
        if self.created_netns:
            destroy_netns(self.created_netns)

    def __enter__(self):
        self.open()

    def __exit__(self, *args):
        self.close()
