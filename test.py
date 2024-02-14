import unittest

class LimiterTest(unittest.TestCase):
    def test_blocker_iplist(self):
        from blocker import Blocker
        iplist = [
            '10.0.0.0-10.255.255.255',
            '100.64.0.0-100.64.255.255',
            '127.0.0.0-127.255.255.255',
            '169.254.0.0-169.254.255.255',
            '172.16.0.0-172.31.255.255',
            '192.168.0.0-192.168.255.255',
            '224.0.0.0-255.255.255.255',
        ]
        b = Blocker({'ip': list(iplist)})
        self.assertListEqual(iplist, list(b.iplist))

    def test_blocker_clientName(self):
        from blocker import Blocker
        b = Blocker({
            'ip': ['10.0.0.0-10.255.255.255'],
            'clientName': [
                {'prefix':   'Xunlei '},
                {'suffix':   ' dev'},
                {'contains': 'anacrolix/torrent'},
                {'equal':    'Free Download Manager 6'}
            ],
            'port': [
                {'equal': 11451},
                {'gt':    37017},
                {'gte':   27017},
                {'lt':    19198},
                {'lte':   19810},
            ]
        })
        self.assertListEqual(['10.0.0.0-10.255.255.255'], list(b.iplist))
        self.assertTrue(b.doFilter({ 'clientName': 'Xunlei (0.0.1.2)'}))
        self.assertTrue(b.doFilter({ 'clientName': 'Taibei-Torrent dev'}))
        self.assertTrue(b.doFilter({ 'clientName': 'trafficConsume (devel) (anacrolix/torrent v1.53.3)'}))
        self.assertTrue(b.doFilter({ 'clientName': 'Free Download Manager 6'}))
        self.assertFalse(b.doFilter({'clientName': 'qBittorrent 4.5.0'}))
        self.assertFalse(b.doFilter({'clientName': 'Free Download Manager 5'}))
        self.assertFalse(b.doFilter({'clientName': 'Transmission 4.0.4'}))
        self.assertFalse(b.doFilter({'clientName': 'bitTorrent 7.10.5'}))
        self.assertFalse(b.doFilter({'clientName': 'μTorrent 2.2.1'}))
        self.assertFalse(b.doFilter({'clientName': 'BoringCat Torrent Dev'}))
        self.assertTrue(b.doFilter({ 'port': 11451}))
        self.assertTrue(b.doFilter({ 'port': 65535}))
        self.assertTrue(b.doFilter({ 'port': 27017}))
        self.assertTrue(b.doFilter({ 'port': 9527}))
        self.assertTrue(b.doFilter({ 'port': 19810}))
        self.assertFalse(b.doFilter({'port': 25316}))

    def test_blocker_empty(self):
        from blocker import Blocker
        b = Blocker(None)
        self.assertListEqual([], list(b.iplist))
        self.assertFalse(b.doFilter({'clientName': 'Xunlei (0.0.1.2)'}))
        self.assertFalse(b.doFilter({'clientName': 'Taibei-Torrent dev'}))
        self.assertFalse(b.doFilter({'clientName': 'trafficConsume (devel) (anacrolix/torrent v1.53.3)'}))
        self.assertFalse(b.doFilter({'clientName': 'Free Download Manager 6'}))
        self.assertFalse(b.doFilter({'clientName': 'qBittorrent 4.5.0'}))
        self.assertFalse(b.doFilter({'clientName': 'Free Download Manager 5'}))
        self.assertFalse(b.doFilter({'clientName': 'Transmission 4.0.4'}))
        self.assertFalse(b.doFilter({'clientName': 'bitTorrent 7.10.5'}))
        self.assertFalse(b.doFilter({'clientName': 'μTorrent 2.2.1'}))
        self.assertFalse(b.doFilter({'clientName': 'BoringCat Torrent Dev'}))
        self.assertFalse(b.doFilter({'port': 11451}))
        self.assertFalse(b.doFilter({'port': 65535}))
        self.assertFalse(b.doFilter({'port': 27017}))
        self.assertFalse(b.doFilter({'port': 9527}))
        self.assertFalse(b.doFilter({'port': 19810}))
        self.assertFalse(b.doFilter({'port': 25316}))
