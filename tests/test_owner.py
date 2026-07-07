import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dzsl.http import RequestError
from dzsl.services import owner

TOKEN = "a" * 64
COOKIE_HEADERS = {**owner.OWNER_HEADERS, "Cookie": f"dzsl_session={TOKEN}"}


def claim_item(**overrides):
    item = {
        "claim": {"serverKey": "1.2.3.4:2302", "status": "verified", "token": "DZSL-ABCD1234"},
        "listing": {
            "serverKey": "1.2.3.4:2302",
            "name": "My Server",
            "description": "desc",
            "discord": "https://discord.gg/x",
            "banner": "https://img.example/b.png",
            "rules": "be nice",
            "promoted": True,
        },
        "verified": True,
        "verifiedExpiresAt": 1780000000000,
        "gold": True,
        "goldUntil": 1790000000000,
        "goldStatus": "active",
    }
    item.update(overrides)
    return item


class SessionStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "owner_session.json")
        self.addCleanup(self.tmp.cleanup)

    def test_round_trip(self):
        owner.save_session(TOKEN, {"steamId": "765611", "persona": "Andy"}, path=self.path)
        session = owner.load_session(self.path)
        self.assertEqual(session["token"], TOKEN)
        self.assertEqual(session["steamId"], "765611")
        self.assertEqual(session["persona"], "Andy")
        self.assertTrue(session["savedAt"] > 0)

    def test_missing_file(self):
        self.assertEqual(owner.load_session(self.path), {})

    def test_corrupt_file(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write("{not json")
        self.assertEqual(owner.load_session(self.path), {})

    def test_invalid_token_rejected(self):
        with open(self.path, "w", encoding="utf-8") as handle:
            handle.write('{"token": "steam; evil=1"}')
        self.assertEqual(owner.load_session(self.path), {})
        with self.assertRaises(ValueError):
            owner.save_session("not-a-token", path=self.path)

    def test_clear(self):
        owner.save_session(TOKEN, path=self.path)
        owner.clear_session(self.path)
        self.assertEqual(owner.load_session(self.path), {})
        owner.clear_session(self.path)  # idempotent


class AuthTest(unittest.TestCase):
    def test_auth_me(self):
        with patch("dzsl.services.owner.request_json", return_value={"user": {"steamId": "7"}}) as request:
            user = owner.auth_me(TOKEN)
        self.assertEqual(user, {"steamId": "7"})
        request.assert_called_once_with(
            "https://dayzlinux.com/api/auth/me", headers=COOKIE_HEADERS, timeout=10
        )

    def test_auth_me_signed_out(self):
        with patch("dzsl.services.owner.request_json", return_value={"user": None}):
            self.assertIsNone(owner.auth_me(TOKEN))

    def test_invalid_token_raises_401(self):
        with self.assertRaises(RequestError) as ctx:
            owner.auth_me("bogus")
        self.assertEqual(ctx.exception.status, 401)

    def test_logout_swallows_errors(self):
        with patch("dzsl.services.owner.request_json", side_effect=RequestError("offline")) as request:
            owner.logout(TOKEN)
        self.assertEqual(request.call_args.kwargs["method"], "POST")


class FetchClaimsTest(unittest.TestCase):
    def test_parses_items(self):
        payload = {
            "items": [
                claim_item(),
                claim_item(gold=False, goldUntil=None, goldStatus=None, verified=False, listing=None),
                {"claim": {"serverKey": "not-a-key"}},
                "garbage",
            ]
        }
        with patch("dzsl.services.owner.request_json", return_value=payload) as request:
            items = owner.fetch_claims(TOKEN)
        request.assert_called_once_with(
            "https://dayzlinux.com/api/claims", headers=COOKIE_HEADERS, timeout=10
        )
        self.assertEqual(len(items), 2)
        first, second = items
        self.assertEqual(first["serverKey"], "1.2.3.4:2302")
        self.assertTrue(first["gold"])
        self.assertEqual(first["goldStatus"], "active")
        self.assertEqual(first["listing"]["name"], "My Server")
        self.assertFalse(second["gold"])
        self.assertFalse(second["verified"])
        self.assertIsNone(second["listing"])

    def test_invalid_payload(self):
        with patch("dzsl.services.owner.request_json", return_value={"nope": 1}):
            with self.assertRaises(RequestError):
                owner.fetch_claims(TOKEN)

    def test_http_status_propagates(self):
        with patch("dzsl.services.owner.request_json", side_effect=RequestError("unauthorized", status=401)):
            with self.assertRaises(RequestError) as ctx:
                owner.fetch_claims(TOKEN)
        self.assertEqual(ctx.exception.status, 401)


class ListingFieldsTest(unittest.TestCase):
    def test_clips_text(self):
        cleaned = owner.clean_listing_fields({"name": " x " + "y" * 300, "rules": "ok"})
        self.assertEqual(len(cleaned["name"]), 120)
        self.assertEqual(cleaned["rules"], "ok")
        self.assertNotIn("description", cleaned)

    def test_rejects_bad_url(self):
        with self.assertRaises(ValueError):
            owner.clean_listing_fields({"discord": "javascript:alert(1)"})
        with self.assertRaises(ValueError):
            owner.clean_listing_fields({"banner": "ftp://x/y.png"})

    def test_empty_url_clears(self):
        cleaned = owner.clean_listing_fields({"discord": "", "banner": "  "})
        self.assertEqual(cleaned, {"discord": "", "banner": ""})

    def test_non_dict_raises(self):
        with self.assertRaises(ValueError):
            owner.clean_listing_fields(None)


class SaveListingTest(unittest.TestCase):
    def test_put_payload(self):
        response = {"listing": claim_item()["listing"]}
        with patch("dzsl.services.owner.request_json", return_value=response) as request:
            listing = owner.save_listing(
                TOKEN,
                "1.2.3.4:2302",
                {"name": "New Name", "discord": "https://discord.gg/x", "description": "d"},
            )
        request.assert_called_once_with(
            "https://dayzlinux.com/api/listings/1.2.3.4%3A2302",
            method="PUT",
            json_body={"name": "New Name", "description": "d", "discord": "https://discord.gg/x"},
            headers=COOKIE_HEADERS,
            timeout=10,
        )
        self.assertEqual(listing["name"], "My Server")
        self.assertTrue(listing["promoted"])

    def test_invalid_key(self):
        with self.assertRaises(ValueError):
            owner.save_listing(TOKEN, "no-port", {"name": "x"})

    def test_invalid_response(self):
        with patch("dzsl.services.owner.request_json", return_value={"listing": None}):
            with self.assertRaises(RequestError):
                owner.save_listing(TOKEN, "1.2.3.4:2302", {"name": "x"})


if __name__ == "__main__":
    unittest.main()
