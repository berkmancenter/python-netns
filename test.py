import unittest, subprocess, os, logging, urllib, time

logging.basicConfig(level=logging.WARNING)

import netns

FIND_HIGHEST_NETNS_SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), 'find_recent_netns.sh')

def find_highest_vpn():
    return subprocess.check_output([FIND_HIGHEST_NETNS_SCRIPT]).decode('utf8').strip()

class TestNetNSCreation(unittest.TestCase):
    def setUp(self):
        self.ns = None
        self.highest = find_highest_vpn()

    def tearDown(self):
        if self.ns:
            self.ns.close()
        # If we error out during the creation of a new namespace, we won't know
        # the name to destroy it. Look one up and only destroy one. This could
        # be wrong, but less work than doing a while loop that isn't too
        # destructive.
        if self.highest != find_highest_vpn():
            netns.destroy_netns('vpn' + find_highest_vpn())

    def test_init_netns_does_not_create_ns(self):
        highest = find_highest_vpn()
        self.ns = netns.NetNS()
        self.assertEqual(highest, find_highest_vpn())

    def test_netns_networking(self):
        with netns.NetNS():
            h = urllib.urlopen('https://example.com')
            self.assertEqual(200, h.getcode())
            h.close()

    def test_netns_without_resolvconf(self):
        with netns.NetNS(resolvconf=False):
            with self.assertRaises(IOError):
                urllib.urlopen('https://example.com')

if __name__ == '__main__':
    unittest.main()
