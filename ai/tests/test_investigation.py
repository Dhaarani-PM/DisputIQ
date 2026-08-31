"""
DisputIQ - Investigation Tests

Tests:
1. Strong evidence
2. Missing evidence
3. Conflicting evidence
4. Duplicate charge
5. Malformed input
"""

import sys
from pathlib import Path

sys.path.insert(
    0,
    str(
        Path(__file__).resolve().parents[1]
    )
)

from investigation import investigate
from result_validator import validate_result


def validate(case):

    raw_result = investigate(case)

    return validate_result(
        raw_result,
        case,
    )


# ============================================================
# TEST 1 - STRONG EVIDENCE
# ============================================================

def test_strong_case():

    case = {
        "dispute": {
            "dispute_id": "T001",
            "reason": "product_not_received",
            "amount": 8499,
        },
        "order": {
            "status": "delivered",
            "amount": 8499,
        },
        "payment": {
            "status": "successful",
            "amount": 8499,
        },
        "delivery": {
            "status": "delivered",
        },
        "sessions": [
            {"event": "order_page_view"}
        ],
        "past_disputes": [],
    }

    result = validate(case)

    assert result["dispute_id"] == "T001"
    assert result["evidence_strength"] == "HIGH"
    assert result["recommendation"] == "CHALLENGE"
    assert 0 <= result["confidence"] <= 1


# ============================================================
# TEST 2 - MISSING EVIDENCE
# ============================================================

def test_missing_delivery():

    case = {
        "dispute": {
            "dispute_id": "T002",
            "reason": "product_not_received",
            "amount": 5000,
        },
        "order": {
            "status": "processing",
            "amount": 5000,
        },
        "payment": {
            "status": "successful",
            "amount": 5000,
        },
        "delivery": None,
        "sessions": [],
        "past_disputes": [],
    }

    result = validate(case)

    assert result["dispute_id"] == "T002"

    assert result["recommendation"] == (
        "NEEDS_MORE_EVIDENCE"
    )

    assert len(
        result["missing_evidence"]
    ) > 0


# ============================================================
# TEST 3 - CONFLICTING EVIDENCE
# ============================================================

def test_conflicting_delivery():

    case = {
        "dispute": {
            "dispute_id": "T003",
            "reason": "product_not_received",
            "amount": 7000,
        },
        "order": {
            "status": "delivered",
            "amount": 7000,
        },
        "payment": {
            "status": "successful",
            "amount": 7000,
        },
        "delivery": {
            "status": "failed",
        },
        "sessions": [],
        "past_disputes": [],
    }

    result = validate(case)

    assert result["recommendation"] == (
        "NEEDS_MORE_EVIDENCE"
    )

    assert (
        "ORDER_DELIVERY_CONFLICT"
        in result["risk_flags"]
    )


# ============================================================
# TEST 4 - DUPLICATE CHARGE
# ============================================================

def test_duplicate_charge():

    case = {
        "dispute": {
            "dispute_id": "T004",
            "reason": "duplicate_charge",
            "amount": 3000,
        },
        "order": {
            "status": "completed",
            "amount": 3000,
        },
        "payment": {
            "status": "successful",
            "amount": 3000,
        },
        "delivery": {
            "status": "delivered",
        },
        "sessions": [],
        "past_disputes": [],
    }

    result = validate(case)

    assert result["recommendation"] == (
        "NEEDS_MORE_EVIDENCE"
    )

    assert any(
        "Duplicate transaction" in item
        for item in result["missing_evidence"]
    )


# ============================================================
# TEST 5 - MALFORMED INPUT
# ============================================================

def test_malformed_input():

    case = {
        "dispute": {
            "dispute_id": "T005",
            "reason": "product_not_received",
            "amount": "hello",
        },
        "order": {
            "status": "delivered",
            "amount": "wrong",
        },
        "payment": {
            "status": "successful",
            "amount": "invalid",
        },
        "delivery": None,
        "sessions": [],
        "past_disputes": [],
    }

    result = validate(case)

    assert result["dispute_id"] == "T005"

    assert result["recommendation"] == (
        "NEEDS_MORE_EVIDENCE"
    )

    assert 0 <= result["confidence"] <= 1