"""Tests with a synthetic save (no real save files in the repo).
Run:  python -m unittest discover -s tests
"""
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import ski_e_o_save_editor as ed  # noqa: E402


def fake_save(balance=-10426):
    def s(text):
        raw = text.encode() + b"\x00"
        return struct.pack("<I", len(raw)) + raw
    prop = (s("Balance") + s("IntProperty") + b"\x00\x00\x00\x00"
            + struct.pack("<I", 4) + b"\x00" + struct.pack("<i", balance))
    decoy = (s("RemainingBalance") + s("IntProperty") + b"\x00\x00\x00\x00"
             + struct.pack("<I", 4) + b"\x00" + struct.pack("<i", 7))
    return b"GVAS" + b"\x03\x00\x00\x00" + b"junk" * 10 + prop + s("ActiveLoans") + decoy


def _s(text):
    raw = text.encode() + b"\x00"
    return struct.pack("<I", len(raw)) + raw


def _prop(name, typ, fmt, value):
    return (_s(name) + _s(typ) + b"\x00\x00\x00\x00" + struct.pack("<I", 4)
            + b"\x00" + struct.pack(fmt, value))


def fake_loans_save(loans):
    """loans: list of (tier, original, remaining, rate, months)."""
    body = b""
    for tier, orig, rem, rate, months in loans:
        body += (_s("Tier") + _s("EnumProperty") + b"\x00" * 8 + _s("ELoanTier") + b"\x00"
                 + _s("ELoanTier::" + tier)
                 + _prop("OriginalPrincipal", "IntProperty", "<i", orig)
                 + _prop("RemainingBalance", "IntProperty", "<i", rem)
                 + _prop("MonthlyInterestRate", "FloatProperty", "<f", rate)
                 + _prop("PaybackMonths", "IntProperty", "<i", months) + b"None\x00")
    return b"GVAS" + b"\x03\x00\x00\x00" + b"junk" * 10 + _s("ActiveLoans") + body


LOANS = [("Small", 190000, 190000, 0.01, 24), ("Medium", 515000, 400000, 0.015, 24),
         ("Large", 1035000, 1035000, 0.02, 24)]


def fake_rep_save(xp=8139, level="RegionalHotspot"):
    """Mirrors the real layout, including the sizes that depend on the level text."""
    lvl = _s("EReputationLevel::" + level)
    body = (_s("CurrentXP") + _s("IntProperty") + b"\x00\x00\x00\x00" + struct.pack("<I", 4)
            + b"\x00" + struct.pack("<i", xp)
            + _s("CurrentLevel") + _s("EnumProperty") + struct.pack("<I", 2) + _s("EReputationLevel")
            + struct.pack("<I", 1) + _s("/Script/SkiResortSimulator") + b"\x00" * 4
            + _s("ByteProperty") + b"\x00" * 4 + struct.pack("<I", len(lvl) - 4 + 4) + b"\x00" + lvl
            + _s("None"))
    block = (_s("ReputationData") + _s("StructProperty") + struct.pack("<I", 1) + _s("ReputationSaveData")
             + b"\x00" * 8 + struct.pack("<I", len(body)) + b"\x00" + body)
    return b"GVAS" + b"\x03\x00\x00\x00" + b"junk" * 10 + block + _s("TutorialData") + b"tail"


class ReputationTests(unittest.TestCase):
    def test_level_change_up_and_down(self):
        data = fake_rep_save()
        for lvl in ("SmallHill", "LegendaryResort", "RegionalHotspot"):
            out = ed.patch_reputation(data, lvl, 0)
            self.assertEqual(ed.read_reputation(out), (0, lvl))
            self.assertEqual(out, fake_rep_save(0, lvl))  # identical to a save the game would write
            self.assertTrue(out.endswith(b"TutorialData\x00" + b"tail") or out.endswith(b"tail"))

    def test_level_only_keeps_xp(self):
        out = ed.patch_reputation(fake_rep_save(5000), "RisingStar")
        self.assertEqual(ed.read_reputation(out), (5000, "RisingStar"))

    def test_thresholds_complete_and_increasing(self):
        t = ed.REPUTATION_XP_TO_NEXT
        self.assertEqual(sorted(t), list(range(1, 14)))  # levels 1-13; 14 is the maximum
        vals = [t[i] for i in range(1, 14)]
        self.assertEqual(vals, sorted(set(vals)))
        self.assertEqual((t[1], t[5], t[7], t[13]), (280, 9050, 35000, 900000))

    def test_level_up_warning(self):
        self.assertEqual(ed.level_up_warning(5, 9049), "")
        self.assertIn("level up", ed.level_up_warning(5, 9050))
        self.assertEqual(ed.level_up_warning(14, 5_000_000), "")

    def test_bad_level_and_nothing(self):
        for args in (("NotALevel", 0), (None, None)):
            with self.assertRaises(ed.EditorError):
                ed.patch_reputation(fake_rep_save(), *args)

    def test_layout_mismatch_refused(self):
        data = fake_rep_save()
        broken = data.replace(b"\x05\x00\x00\x00None\x00", b"\x05\x00\x00\x00Nonx\x00", 1)
        with self.assertRaises(ed.EditorError):
            ed.patch_reputation(broken, "SmallHill", 0)

    def test_read(self):
        self.assertEqual(ed.read_reputation(fake_rep_save()), (8139, "RegionalHotspot"))

    def test_none_when_missing(self):
        self.assertIsNone(ed.read_reputation(b"GVAS" + b"\x00" * 50))

    def test_patch(self):
        data = fake_rep_save()
        out = ed.patch_reputation(data, None, 1_000_000)
        self.assertEqual(len(out), len(data))
        self.assertEqual(ed.read_reputation(out), (1_000_000, "RegionalHotspot"))
        self.assertTrue(sum(a != b for a, b in zip(data, out)) <= 4)

    def test_validation(self):
        for bad in (-1, 2**31, "5", 1.5):
            with self.assertRaises(ed.EditorError):
                ed.patch_reputation(fake_rep_save(), None, bad)

    def test_pretty_and_levels(self):
        self.assertEqual(ed.pretty_level("RegionalHotspot"), "Regional Hotspot")
        self.assertEqual(len(ed.REPUTATION_LEVELS), 14)
        self.assertEqual(ed.REPUTATION_LEVELS[13], "LegendaryResort")


def fake_staff_save(staff):
    """staff: list of (role, wage, xp, promotions, stamina). A hiring pool with look-alike
    fields follows the roster; it must never be touched."""
    def person(role, wage, xp, promo, stamina):
        return (_s("Role") + _s("EnumProperty") + _s("EStaffRole::" + role)
                + _prop("DailyWage", "IntProperty", "<i", wage) + _prop("XP", "IntProperty", "<i", xp)
                + _prop("PromotionsApplied", "IntProperty", "<i", promo)
                + _prop("Stamina", "FloatProperty", "<f", stamina))
    roster = b"".join(person(*p) for p in staff)
    pool = person("Liftie", 384, 0, 0, 100.0).replace(b"EStaffRole::", b"EStaffRolX::")
    return (b"GVAS" + b"\x03\x00\x00\x00" + b"junk" * 10 + _s("Roster") + _s("ArrayProperty")
            + roster + _s("HiringPool") + _s("ArrayProperty") + pool + b"tail")


STAFF = [("Liftie", 100, 10, 0, 50.0), ("Groomer", 200, 20, 1, 80.0),
         ("Liftie", 120, 30, 0, 100.0), ("SkiPatrol", 250, 0, 2, 40.0)]


class BackupTests(unittest.TestCase):
    def test_old_and_new_backup_folders_are_both_listed(self):
        import tempfile
        with tempfile.TemporaryDirectory() as docs:
            ed_docs = ed.documents_dir
            ed.documents_dir = lambda: docs
            try:
                for root, stamp in ((ed.legacy_backup_root(), "2026-01-01_10-00-00"),
                                    (ed.backup_root(), "2026-02-01_10-00-00")):
                    d = os.path.join(root, stamp)
                    os.makedirs(d)
                    with open(os.path.join(d, "slot.sav"), "wb") as f:
                        f.write(fake_save(123))
                found = ed.list_backups()
                self.assertEqual([e["stamp"] for e in found], ["2026-02-01_10-00-00", "2026-01-01_10-00-00"])
                self.assertEqual([e["balance"] for e in found], [123, 123])
            finally:
                ed.documents_dir = ed_docs


class StaffTests(unittest.TestCase):
    def test_find_and_summary(self):
        s = ed.find_staff(fake_staff_save(STAFF))
        self.assertEqual([x["role"] for x in s], ["Liftie", "Groomer", "Liftie", "SkiPatrol"])
        self.assertEqual((s[1]["wage"], s[1]["xp"], s[1]["promotions"]), (200, 20, 1))
        summ = {r["role"]: r for r in ed.staff_summary(s)}
        self.assertEqual(summ["Liftie"]["count"], 2)
        self.assertEqual(summ["Liftie"]["wage"], 110)

    def test_no_staff(self):
        self.assertEqual(ed.find_staff(b"GVAS" + b"\x00" * 50), [])

    def test_patch_scope_and_hiring_pool_untouched(self):
        data = fake_staff_save(STAFF)
        staff = ed.find_staff(data)
        ch = ed.build_staff_changes(staff, ["Liftie"], wage=("set", 1), stamina=100.0)
        out = ed.patch_staff(data, ch)
        self.assertEqual(len(out), len(data))
        a = ed.find_staff(out)
        self.assertEqual([(x["wage"], x["stamina"]) for x in a],
                         [(1, 100.0), (200, 80.0), (1, 100.0), (250, 40.0)])
        self.assertEqual(out[out.index(ed._fstring("HiringPool")):], data[data.index(ed._fstring("HiringPool")):])

    def test_scale_and_minimum_wage(self):
        staff = ed.find_staff(fake_staff_save(STAFF))
        ch = ed.build_staff_changes(staff, None, wage=("scale", 0.5))
        self.assertEqual([ch[i]["wage"] for i in range(4)], [50, 100, 60, 125])
        ch = ed.build_staff_changes(staff, None, wage=("scale", 0.0001))
        self.assertTrue(all(c["wage"] == 1 for c in ch.values()))

    def test_xp_only(self):
        data = fake_staff_save(STAFF)
        ch = ed.build_staff_changes(ed.find_staff(data), ["Groomer"], xp=5000)
        a = ed.find_staff(ed.patch_staff(data, ch))
        self.assertEqual([x["xp"] for x in a], [10, 5000, 30, 0])

    def test_validation(self):
        data = fake_staff_save(STAFF)
        for bad in ({0: {"wage": -1}}, {0: {"xp": 2**31}}, {0: {"stamina": 101.0}},
                    {0: {"stamina": -1.0}}, {9: {"wage": 5}}):
            with self.assertRaises(ed.EditorError):
                ed.patch_staff(data, bad)

    def test_parse_wage_spec(self):
        self.assertEqual(ed.parse_wage_spec("150"), ("set", 150))
        self.assertEqual(ed.parse_wage_spec("50%"), ("scale", 0.5))
        self.assertIsNone(ed.parse_wage_spec(""))
        for bad in ("0", "abc", "0%", "5000%", "-5"):
            with self.assertRaises(ed.EditorError):
                ed.parse_wage_spec(bad)

    def test_mismatched_fields_refused(self):
        data = fake_staff_save(STAFF)
        broken = data.replace(ed._fstring("Stamina"), ed._fstring("Staminx"), 1)
        with self.assertRaises(ed.EditorError):
            ed.find_staff(broken)


class LoanTests(unittest.TestCase):
    def test_find(self):
        loans = ed.find_loans(fake_loans_save(LOANS))
        self.assertEqual([l["tier"] for l in loans], ["Small", "Medium", "Large"])
        self.assertEqual([l["remaining"] for l in loans], [190000, 400000, 1035000])
        self.assertAlmostEqual(loans[1]["rate"], 0.015, places=6)

    def test_no_loans(self):
        self.assertEqual(ed.find_loans(b"GVAS" + b"\x00" * 50), [])

    def test_patch_only_selected_values(self):
        data = fake_loans_save(LOANS)
        out = ed.patch_loans(data, {0: {"remaining": 0}, 1: {"rate": 0.0}, 2: {"remaining": 5, "rate": 0.05}})
        self.assertEqual(len(out), len(data))
        a = ed.find_loans(out)
        self.assertEqual((a[0]["remaining"], a[1]["remaining"], a[2]["remaining"]), (0, 400000, 5))
        self.assertEqual(a[1]["rate"], 0.0)
        self.assertAlmostEqual(a[0]["rate"], 0.01, places=6)  # untouched
        self.assertEqual(a[2]["rate"], ed.f32(0.05))
        self.assertEqual([l["original"] for l in a], [190000, 515000, 1035000])

    def test_validation(self):
        data = fake_loans_save(LOANS)
        for bad in ({0: {"remaining": -1}}, {0: {"remaining": 2**31}}, {0: {"rate": -0.1}},
                    {0: {"rate": 1.5}}, {7: {"remaining": 0}}):
            with self.assertRaises(ed.EditorError):
                ed.patch_loans(data, bad)

    def test_mismatched_fields_refused(self):
        data = fake_loans_save(LOANS)
        broken = data.replace(ed._fstring("PaybackMonths"), ed._fstring("PaybackMonthX"), 1)
        with self.assertRaises(ed.EditorError):
            ed.find_loans(broken)

    def test_parse_percent(self):
        self.assertAlmostEqual(ed.parse_percent("1,5"), 0.015)
        self.assertAlmostEqual(ed.parse_percent("0 %"), 0.0)
        with self.assertRaises(ed.EditorError):
            ed.parse_percent("abc")
        with self.assertRaises(ed.EditorError):
            ed.parse_percent("150")


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
