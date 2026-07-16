"""Shared fixture data for the eaitl held-out suite.

Deliberately imports nothing from `eaitl` so that the one base-passing
regression guard can run even when the package does not exist yet.
"""

# --- The worked example, transcribed from design-draft.md -------------------
#
# `sample_rows[0]` of the POST /propose-mappings example request, and the
# `proposed_mappings` of the example response. The draft's own
# `example_output_rows` / `preview_rows` are the oracle.

DRAFT_ROW = {
    "order_id": "A1001",
    "customer_first_name": "Ada",
    "customer_last_name": "Lovelace",
    "amount_cents": 2599,
    "created_at": "2026-07-10T14:22:11Z",
    "status": "paid",
}

DRAFT_EXPECTED_ROW = {
    "id": "A1001",
    "customer_name": "Ada Lovelace",
    "amount_usd": 25.99,
    "order_date": "2026-07-10",
    "is_paid": True,
}

# The full IR, carrying every key the draft shows. `job_id`, `source`,
# `target` and `validations` are proposal metadata the engine must ignore;
# so are the per-mapping `sources`, `type`, `confidence`, `rationale` and
# `status` keys. They are present here precisely so that an engine which
# reads them (rather than ignoring them) is caught.
DRAFT_IR = {
    "job_id": "job_123",
    "source": {"name": "raw_orders", "format": "json"},
    "target": {"name": "analytics_orders"},
    "mappings": [
        {
            "target_field": "id",
            "sources": ["order_id"],
            "transform": {"op": "copy", "args": ["order_id"]},
            "type": "string",
            "confidence": 0.99,
            "status": "proposed",
        },
        {
            "target_field": "customer_name",
            "sources": ["customer_first_name", "customer_last_name"],
            "transform": {
                "op": "concat",
                "args": ["customer_first_name", " ", "customer_last_name"],
            },
            "type": "string",
            "confidence": 0.97,
            "rationale": "Target example matches joined first and last name",
            "status": "proposed",
        },
        {
            "target_field": "amount_usd",
            "sources": ["amount_cents"],
            "transform": {"op": "divide", "args": ["amount_cents", 100]},
            "type": "float",
            "confidence": 0.96,
            "status": "proposed",
        },
        {
            "target_field": "order_date",
            "sources": ["created_at"],
            "transform": {"op": "to_date", "args": ["created_at"]},
            "type": "date",
            "confidence": 0.94,
            "status": "proposed",
        },
        {
            "target_field": "is_paid",
            "sources": ["status"],
            "transform": {"op": "equals", "args": ["status", "paid"]},
            "type": "boolean",
            "confidence": 0.91,
            "status": "proposed",
        },
    ],
    "filters": [],
    "validations": [
        {"kind": "not_null", "field": "id"},
        {"kind": "type_check", "field": "amount_usd", "expected": "float"},
    ],
}


# --- Tiny IR builders ------------------------------------------------------

def mapping(target_field, op, *args):
    """A single mapping entry: target_field <- op(*args)."""
    return {
        "target_field": target_field,
        "transform": {"op": op, "args": list(args)},
    }


def predicate(op, *args):
    """A single filter entry."""
    return {"op": op, "args": list(args)}


def make_ir(mappings, filters=None):
    """An IR carrying only what the engine reads."""
    ir = {"mappings": list(mappings)}
    if filters is not None:
        ir["filters"] = list(filters)
    return ir


def one_op_ir(target_field, op, *args):
    """The common case: an IR with exactly one mapping."""
    return make_ir([mapping(target_field, op, *args)])


# --- Assertions on the pinned error-record shape ---------------------------

ERROR_KEYS = {"row_index", "target_field", "reason"}


class ErrorShapeMixin:
    """Shared checks for the `{row_index, target_field, reason}` record.

    A plain mixin, not a TestCase, so unittest never tries to collect it.
    """

    def assertErrorShape(self, err):
        self.assertIsInstance(err, dict, "each errors entry must be a dict")
        self.assertEqual(
            ERROR_KEYS,
            set(err),
            "an errors entry must carry exactly row_index, target_field and reason",
        )
        self.assertIsInstance(err["row_index"], int)
        self.assertNotIsInstance(
            err["row_index"], bool, "row_index must be an int, not a bool"
        )
        if err["target_field"] is not None:
            self.assertIsInstance(err["target_field"], str)
        self.assertIsInstance(err["reason"], str)
        self.assertTrue(err["reason"].strip(), "reason must be a non-empty string")

    def assertErrorsMatch(self, errors, expected):
        """`expected` is a list of (row_index, target_field) pairs, order-free."""
        self.assertIsInstance(errors, list)
        for err in errors:
            self.assertErrorShape(err)
        self.assertCountEqual(
            expected,
            [(e["row_index"], e["target_field"]) for e in errors],
            f"unexpected error records: {errors!r}",
        )
