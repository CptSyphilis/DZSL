import unittest

import workshop_gate


class WorkshopGateTests(unittest.TestCase):
    def tearDown(self):
        workshop_gate.finish()

    def test_rejects_overlapping_operation(self):
        acquired, _ = workshop_gate.try_begin("Downloading server mods")
        second, active = workshop_gate.try_begin("Verifying all mods")

        self.assertTrue(acquired)
        self.assertFalse(second)
        self.assertEqual(active, "Downloading server mods")

    def test_finish_allows_next_operation(self):
        workshop_gate.try_begin("First")
        workshop_gate.finish()

        acquired, active = workshop_gate.try_begin("Second")

        self.assertTrue(acquired)
        self.assertEqual(active, "")


if __name__ == "__main__":
    unittest.main()
