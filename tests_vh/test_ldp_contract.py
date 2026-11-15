"""Handwritten contracts for the existing ledger; protected ldp stays unchanged."""

import importlib
import unittest

from ldp.ledger import Job, Ledger, Out, St


class LdpContractTests(unittest.TestCase):
    def test_voice_harness_package_imports(self):
        package = importlib.import_module("vh")
        self.assertIsNotNone(package.__path__)

    def test_stop_announced_job_is_dropped(self):
        ledger = Ledger()
        job = ledger.add("pending_action", "chg", 100)
        self.assertIsInstance(job, Job)
        ledger.announce(job)
        self.assertEqual(job.state, St.ANNOUNCED)

        outcome = ledger.stop(job, 20)

        self.assertEqual(outcome, Out.DROPPED)
        self.assertEqual(job.state, St.CANCELLED)
        self.assertEqual(job.t_end, 20)

    def test_stop_committed_changing_job_is_too_late(self):
        ledger = Ledger()
        job = ledger.add("committed_action", "chg", 100, reversible=False)
        self.assertIsInstance(job, Job)
        ledger.start(job, 0)
        job.committed = True
        self.assertEqual(job.state, St.RUNNING_CHG)

        outcome = ledger.stop(job, 20)

        self.assertEqual(outcome, Out.TOO_LATE)
        self.assertEqual(job.state, St.RUNNING_CHG)
        self.assertTrue(job.committed)
        self.assertIsNone(job.t_end)

    def test_stop_protected_running_read_only_job_is_protected(self):
        ledger = Ledger()
        job = ledger.add("protected_query", "ro", 100)
        self.assertIsInstance(job, Job)
        ledger.start(job, 0)
        ledger.protected.add(job.name)
        self.assertEqual(job.state, St.RUNNING_RO)

        outcome = ledger.stop(job, 20)

        self.assertEqual(outcome, Out.PROTECTED)
        self.assertEqual(job.state, St.RUNNING_RO)
        self.assertIsNone(job.t_end)

    def test_finish_irreversible_changing_job_is_done_irreversible(self):
        ledger = Ledger()
        job = ledger.add("irreversible_action", "chg", 100, reversible=False)
        self.assertIsInstance(job, Job)
        ledger.start(job, 0)
        self.assertEqual(job.state, St.RUNNING_CHG)

        ledger.finish(job, 100)

        self.assertEqual(job.state, St.DONE_IRREV)
        self.assertEqual(job.t_end, 100)
        # Ledger completion alone does not execute or commit a backend effect.
        self.assertFalse(job.committed)


if __name__ == "__main__":
    unittest.main()
