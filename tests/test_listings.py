import unittest
from unittest.mock import patch

from dzsl.http import RequestError
from dzsl.services import listings


class GoldListingTests(unittest.TestCase):
    def setUp(self):
        listings._featured_cache = {}
        listings._featured_cache_at = 0

    def test_featured_listings_are_validated_and_cached(self):
        payload = {
            "featured": [
                {
                    "serverKey": "203.0.113.8:2302",
                    "name": " Gold Server ",
                    "description": "Featured",
                    "discord": "https://discord.gg/example",
                    "banner": "https://example.com/banner.png",
                    "promoted": True,
                    "updatedAt": 10,
                },
                {"serverKey": "bad", "promoted": True},
                {"serverKey": "203.0.113.9:2302", "promoted": False},
            ]
        }
        with patch("dzsl.services.listings.get_json", return_value=payload) as request:
            first = listings.featured_listings(now=100)
            second = listings.featured_listings(now=101)

        self.assertEqual(list(first), ["203.0.113.8:2302"])
        self.assertEqual(first["203.0.113.8:2302"]["name"], "Gold Server")
        self.assertEqual(first, second)
        request.assert_called_once_with(
            "https://dayzlinux.com/api/listings",
            headers=listings.LISTINGS_HEADERS,
            timeout=8,
        )

    def test_stale_cache_is_used_when_api_fails(self):
        listings._featured_cache = {"203.0.113.8:2302": {"promoted": True}}
        listings._featured_cache_at = 1
        with patch("dzsl.services.listings.get_json", side_effect=RequestError("offline")):
            result = listings.featured_listings(now=1000)
        self.assertIn("203.0.113.8:2302", result)

    def test_attach_matches_string_and_integer_ports(self):
        servers = [{"ip": "203.0.113.8", "port": 2302}, {"ip": "203.0.113.9", "port": "2302"}]
        gold = {"203.0.113.8:2302": {"promoted": True}}
        listings.attach_featured_listings(servers, gold)
        self.assertTrue(servers[0]["_gold_listing"]["promoted"])
        self.assertNotIn("_gold_listing", servers[1])

    def test_gold_servers_are_pinned_without_reordering_groups(self):
        servers = [
            {"name": "normal-one"},
            {"name": "gold-one", "_gold_listing": {"promoted": True}},
            {"name": "normal-two"},
            {"name": "gold-two", "_gold_listing": {"promoted": True}},
        ]
        result = listings.pin_featured_servers(servers)
        self.assertEqual(
            [server["name"] for server in result],
            ["gold-one", "gold-two", "normal-one", "normal-two"],
        )


if __name__ == "__main__":
    unittest.main()
