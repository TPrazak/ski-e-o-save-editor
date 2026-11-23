"""Tests with a synthetic save (no real save files in the repo).
Run:  python -m unittest discover -s tests
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ski_e_o_balance_editor as ed  # noqa: E402


def fake_save(balance=-10426):
    def s(text):
        raw = text.encode() + b"\x00"
        return struct.pack("<I", len(raw)) + raw
    prop = (s("Balance") + s("IntProperty") + b"\x00\x00\x00\x00"
            + struct.pack("<I", 4) + b"\x00" + struct.pack("<i", balance))
    decoy = (s("RemainingBalance") + s("IntProperty") + b"\x00\x00\x00\x00"
             + struct.pack("<I", 4) + b"\x00" + struct.pack("<i", 7))
    return b"GVAS" + b"\x03\x00\x00\x00" + b"junk" * 10 + prop + s("ActiveLoans") + decoy


class CoreTests(unittest.TestCase):
    def test_read(self):
        self.assertEqual(ed.read_balance(fake_save(-10426)), -10426)

    def test_patch_changes_only_four_bytes(self):
        a = fake_save(5)
        b = ed.patch_balance(a, 2_000_000)
        self.assertEqual(len(a), len(b))
        self.assertEqual(ed.read_balance(b), 2_000_000)
        self.assertEqual(sum(x != y for x, y in zip(a, b)) <= 4, True)

    def test_range(self):
        with self.assertRaises(ed.EditorError):
            ed.patch_balance(fake_save(), 2**31)

    def test_not_a_save(self):
        with self.assertRaises(ed.EditorError):
            ed.read_balance(b"hello world")

    def test_missing_balance(self):
        with self.assertRaises(ed.EditorError):
            ed.read_balance(b"GVAS" + b"\x00" * 100)

    def test_parse_amount(self):
        self.assertEqual(ed.parse_amount("2,000,000"), 2000000)
        with self.assertRaises(ed.EditorError):
            ed.parse_amount("abc")


if __name__ == "__main__":
    unittest.main()
