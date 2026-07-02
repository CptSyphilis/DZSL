import unittest

from dzsl.core.uri import parse_connect_uri, validate_host_port


class ConnectUriTests(unittest.TestCase):
    def test_parses_ipv4_connect_uri(self):
        self.assertEqual(
            parse_connect_uri("dzsl://connect/203.0.113.10/2302"),
            ("203.0.113.10", 2302),
        )

    def test_parses_hostname_connect_uri(self):
        self.assertEqual(
            parse_connect_uri("dzsl://connect/dayz.example.com/2302"),
            ("dayz.example.com", 2302),
        )

    def test_rejects_unexpected_action(self):
        with self.assertRaises(ValueError):
            parse_connect_uri("dzsl://delete/dayz.example.com/2302")

    def test_rejects_query_and_fragment(self):
        for uri in (
            "dzsl://connect/dayz.example.com/2302?password=secret",
            "dzsl://connect/dayz.example.com/2302#fragment",
        ):
            with self.subTest(uri=uri), self.assertRaises(ValueError):
                parse_connect_uri(uri)

    def test_rejects_invalid_host(self):
        with self.assertRaises(ValueError):
            validate_host_port("bad host", 2302)

    def test_rejects_out_of_range_port(self):
        for port in (0, 65536, "invalid"):
            with self.subTest(port=port), self.assertRaises(ValueError):
                validate_host_port("dayz.example.com", port)


if __name__ == "__main__":
    unittest.main()
