import unittest

from dzsl.core.uri import parse_connect_uri


class ParseConnectUriTests(unittest.TestCase):
    def test_parses_ipv4_server(self):
        self.assertEqual(
            parse_connect_uri("dzsl://connect/193.25.252.82/2302"),
            ("193.25.252.82", 2302),
        )

    def test_parses_hostname(self):
        self.assertEqual(
            parse_connect_uri("dzsl://connect/dayz.example.net/2402"),
            ("dayz.example.net", 2402),
        )

    def test_rejects_wrong_action(self):
        with self.assertRaises(ValueError):
            parse_connect_uri("dzsl://delete/193.25.252.82/2302")

    def test_rejects_out_of_range_port(self):
        with self.assertRaises(ValueError):
            parse_connect_uri("dzsl://connect/193.25.252.82/70000")

    def test_rejects_extra_data(self):
        with self.assertRaises(ValueError):
            parse_connect_uri("dzsl://connect/193.25.252.82/2302?password=nope")


if __name__ == "__main__":
    unittest.main()
