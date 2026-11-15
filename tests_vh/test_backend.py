"""Staging backend expectations from the fixture specified in decision D11."""

from copy import deepcopy
import unittest

from vh.backend import Backend
from vh.tools import TOOLS, summary, tool_schemas, validate_args


def initial():
    return {"services": {"checkout-api": {
        "environment": "staging", "active_release": "12",
        "rollback_targets": ["10", "11"],
    }}}


STATUS = {"service": "checkout-api"}
ROLLBACK = {"service": "checkout-api", "release": "11"}


class BackendTests(unittest.TestCase):
    def test_status_is_read_only_and_returns_detached_data(self):
        backend = Backend(initial())
        before = backend.state_hash()
        reply = backend.apply("get_deployment_status", STATUS)
        self.assertEqual(reply, {
            "service": "checkout-api", "environment": "staging",
            "active_release": "12", "rollback_targets": ["10", "11"],
        })
        self.assertEqual(backend.audit, [])
        self.assertEqual(backend.state_hash(), before)
        reply["rollback_targets"].clear()
        self.assertEqual(backend.snapshot(), initial())

    def test_rollback_changes_only_active_release_and_records_audit(self):
        original = initial()
        args = dict(ROLLBACK)
        backend = Backend(original)
        before = backend.state_hash()
        self.assertEqual(before, Backend(initial()).state_hash())
        result = backend.apply("rollback_deployment", args)
        self.assertEqual(result, {
            "service": "checkout-api", "environment": "staging",
            "previous_release": "12", "active_release": "11",
        })
        expected = initial()
        expected["services"]["checkout-api"]["active_release"] = "11"
        self.assertEqual(backend.snapshot(), expected)
        self.assertNotEqual(backend.state_hash(), before)
        self.assertEqual(backend.state_hash(), Backend(expected).state_hash())
        args["release"] = "10"
        self.assertEqual(backend.audit, [
            {"tool": "rollback_deployment", "args": ROLLBACK,
             "before": original, "after": expected},
        ])
        self.assertEqual(original, initial())

    def test_snapshot_and_original_are_isolated(self):
        original = initial()
        backend = Backend(original)
        snapshot = backend.snapshot()
        snapshot["services"]["checkout-api"]["active_release"] = "99"
        original["services"]["checkout-api"]["rollback_targets"].append("99")
        self.assertEqual(backend.snapshot(), initial())

    def test_bad_calls_fail_without_an_audit_or_mutation(self):
        backend = Backend(initial())
        cases = [
            ("unknown", {}, "unknown_tool"),
            ("get_deployment_status", [], "invalid_args"),
            ("get_deployment_status", {}, "unexpected_args"),
            ("get_deployment_status", {"service": "production"}, "unknown_service"),
            ("rollback_deployment", {**ROLLBACK, "environment": "prod"}, "unexpected_args"),
            ("rollback_deployment", {**ROLLBACK, "release": "1"}, "invalid_release"),
            ("rollback_deployment", {**ROLLBACK, "release": 11}, "invalid_release"),
            ("rollback_deployment", {**ROLLBACK, "release": "１１"}, "invalid_release"),
            ("rollback_deployment", {**ROLLBACK, "release": "13"}, "unknown_release"),
        ]
        for name, args, reason in cases:
            with self.subTest(name=name, args=args):
                self.assertEqual(validate_args(name, args), [reason])
                with self.assertRaisesRegex(ValueError, f"^{reason}$"):
                    backend.apply(name, args)
                self.assertEqual(backend.snapshot(), initial())
                self.assertEqual(backend.audit, [])

    def test_duplicate_active_release_is_rejected(self):
        backend = Backend(initial())
        backend.apply("rollback_deployment", ROLLBACK)
        before = backend.snapshot()
        with self.assertRaisesRegex(ValueError, "^already_active$"):
            backend.apply("rollback_deployment", ROLLBACK)
        self.assertEqual(backend.snapshot(), before)
        self.assertEqual(len(backend.audit), 1)

    def test_timeout_occurs_before_mutation_and_one_retry_can_succeed(self):
        backend = Backend(initial(), fault="timeout_first")
        backend.apply("get_deployment_status", STATUS)
        with self.assertRaisesRegex(TimeoutError, "^timeout$"):
            backend.apply("rollback_deployment", ROLLBACK)
        self.assertEqual(backend.snapshot(), initial())
        self.assertEqual(backend.audit, [])
        self.assertEqual(backend.apply("rollback_deployment", ROLLBACK)["active_release"], "11")
        self.assertEqual(len(backend.audit), 1)

    def test_tool_schemas_describe_exact_allowlisted_inputs(self):
        schemas = tool_schemas()
        self.assertEqual([item["type"] for item in schemas], ["function", "function"])
        functions = {item["function"]["name"]: item["function"] for item in schemas}
        self.assertEqual(set(functions), {"get_deployment_status", "rollback_deployment"})
        self.assertEqual(TOOLS["get_deployment_status"].kind, "ro")
        self.assertEqual(TOOLS["rollback_deployment"].kind, "irrev")
        for name, expected in {
            "get_deployment_status": {"service"},
            "rollback_deployment": {"service", "release"},
        }.items():
            function = functions[name]
            self.assertTrue(function["description"])
            self.assertEqual(set(function["parameters"]["required"]), expected)
            self.assertEqual(set(function["parameters"]["properties"]), expected)
            self.assertIs(function["parameters"]["additionalProperties"], False)
        pristine = deepcopy(tool_schemas())
        functions["rollback_deployment"]["parameters"]["properties"].clear()
        self.assertEqual(tool_schemas(), pristine)

    def test_summary_uses_observed_backend_state(self):
        backend = Backend(initial())
        result = backend.apply("rollback_deployment", ROLLBACK)
        self.assertEqual(summary("rollback_deployment", ROLLBACK, result),
                         "staging checkout-api is now on release 11")
