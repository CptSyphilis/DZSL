import os
import tempfile
import unittest

from dzsl.steam.login import (
    SteamAccount,
    connection_logged_on,
    read_login_account,
    steam_login_account,
)


LOGIN_USERS = '''
"users"
{
    "76561198000000001"
    {
        "AccountName" "older"
        "PersonaName" "Older User"
        "MostRecent" "0"
        "Timestamp" "100"
    }
    "76561198000000002"
    {
        "AccountName" "current"
        "PersonaName" "Current User"
        "MostRecent" "1"
        "Timestamp" "200"
    }
}
'''


class SteamLoginTests(unittest.TestCase):
    def test_reads_most_recent_login_user(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "loginusers.vdf")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(LOGIN_USERS)

            account = read_login_account((path,))

        self.assertEqual(
            account,
            SteamAccount("76561198000000002", "current", "Current User"),
        )

    def test_connection_state_uses_last_log_entry(self):
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "connection_log.txt")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(
                    "[2026-07-04 10:00:00] [Logged On, 4, 1] connected\n"
                    "[2026-07-04 10:01:00] [Logged Off, 0, 0] disconnected\n"
                )
            self.assertFalse(connection_logged_on((path,)))

    def test_gate_requires_ready_client_and_logged_on_state(self):
        with tempfile.TemporaryDirectory() as directory:
            users = os.path.join(directory, "loginusers.vdf")
            log = os.path.join(directory, "connection_log.txt")
            with open(users, "w", encoding="utf-8") as handle:
                handle.write(LOGIN_USERS)
            with open(log, "w", encoding="utf-8") as handle:
                handle.write("[2026-07-04 10:00:00] [Logged On, 4, 1] connected\n")

            self.assertIsNone(
                steam_login_account(lambda: False, (users,), (log,))
            )
            account = steam_login_account(lambda: True, (users,), (log,))

        self.assertEqual(account.display_name, "Current User")


if __name__ == "__main__":
    unittest.main()
