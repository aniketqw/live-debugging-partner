"""M0: the ledger table from SESSIONS.md section 2, row by row."""
import unittest

from ldp.ledger import Ledger, Out, St


def make(state, kind="chg", reversible=True, pausable=False, committed=False):
    L = Ledger()
    j = L.add("job", kind, 10_000, reversible=reversible, pausable=pausable)
    j.state, j.committed = state, committed
    return L, j


class LedgerTable(unittest.TestCase):
    def test_hold(self):
        for state, kind, pausable, want in [
            (St.PROPOSED, "chg", False, "kept_pending"),
            (St.ANNOUNCED, "chg", False, "kept_pending"),
            (St.RUNNING_RO, "ro", False, "continue"),
            (St.RUNNING_CHG, "chg", True, "paused"),
            (St.RUNNING_CHG, "chg", False, "finish_step"),
            (St.DONE_REV, "chg", False, "n/a"),
            (St.DONE_IRREV, "chg", False, "n/a"),
        ]:
            L, j = make(state, kind, pausable=pausable)
            self.assertEqual(L.hold(j), want, (state, pausable))

    def test_stop(self):
        cases = [
            (St.PROPOSED, "chg", False, Out.DROPPED),
            (St.ANNOUNCED, "chg", False, Out.DROPPED),
            (St.RUNNING_RO, "ro", False, Out.CANCELLED),
            (St.RUNNING_CHG, "chg", False, Out.CANCELLED),     # before the commit point: safe
            (St.RUNNING_CHG, "chg", True, Out.TOO_LATE),       # past the commit point
            (St.DONE_REV, "chg", False, Out.DONE_REV),
            (St.DONE_IRREV, "chg", False, Out.DONE_IRREV),
        ]
        for state, kind, committed, want in cases:
            L, j = make(state, kind, committed=committed)
            self.assertEqual(L.stop(j, 5), want, (state, committed))

    def test_stop_marks_state(self):
        L, j = make(St.RUNNING_RO, "ro")
        L.stop(j, 5)
        self.assertEqual(j.state, St.CANCELLED)
        L, j = make(St.RUNNING_CHG, committed=True)
        L.stop(j, 5)
        self.assertEqual(j.state, St.RUNNING_CHG)            # too late: the job goes on

    def test_keep_job_protects_read_only_work(self):
        L, j = make(St.RUNNING_RO, "ro")
        L.protected.add("job")
        self.assertEqual(L.stop(j, 5), Out.PROTECTED)
        self.assertEqual(j.state, St.RUNNING_RO)
        self.assertEqual(L.stop(j, 5, force=True), Out.CANCELLED)   # a naive stop-all ignores it

    def test_undo(self):
        L, j = make(St.DONE_REV)
        self.assertEqual(L.undo(j), Out.UNDO_OK)
        self.assertEqual(j.state, St.UNDONE)
        L, j = make(St.DONE_IRREV, reversible=False)
        self.assertEqual(L.undo(j), Out.DONE_IRREV)
        L, j = make(St.RUNNING_RO, "ro")
        self.assertEqual(L.undo(j), Out.NOOP)

    def test_pause_and_resume(self):
        L, j = make(St.RUNNING_CHG, pausable=True)
        self.assertTrue(L.pause(j, "onset"))
        self.assertEqual(j.state, St.PAUSED)
        L.resume(j)
        self.assertEqual(j.state, St.RUNNING_CHG)
        L, j = make(St.RUNNING_CHG, pausable=False)
        self.assertFalse(L.pause(j, "onset"))

    def test_finish_states(self):
        L = Ledger()
        ro = L.add("a", "ro", 1000)
        rev = L.add("b", "chg", 1000, reversible=True)
        irr = L.add("c", "chg", 1000, reversible=False)
        for j in (ro, rev, irr):
            L.finish(j, 1)
        self.assertEqual([ro.state, rev.state, irr.state], [St.DONE_REV, St.DONE_REV, St.DONE_IRREV])


if __name__ == "__main__":
    unittest.main()
