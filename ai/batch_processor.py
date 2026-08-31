"""
DisputIQ - Batch Investigation Processor

Step 5

Processes multiple structured dispute cases and returns
one validated investigation result for each case.

Important:
- Every result keeps its original dispute_id.
- One bad case does not crash the entire batch.
- Invalid cases receive NEEDS_MORE_EVIDENCE.
"""

import json
from typing import Any, Dict, List

from investigation import investigate
from result_validator import validate_result


# ============================================================
# SINGLE CASE
# ============================================================

def process_case(
    case: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Process one dispute case.

    Flow:

        Case
          ↓
        Investigation
          ↓
        Result Validator
          ↓
        Safe Result
    """

    try:

        raw_result = investigate(case)

        validated_result = validate_result(
            raw_result,
            case,
        )

        return validated_result

    except Exception as exc:

        dispute_id = (
            case
            .get("dispute", {})
            .get("dispute_id")
            if isinstance(case, dict)
            else None
        )

        return {
            "dispute_id": dispute_id,
            "evidence_strength": "INSUFFICIENT",
            "confidence": 0.0,
            "recommendation": "NEEDS_MORE_EVIDENCE",
            "reasoning": (
                "The investigation could not be completed "
                "reliably because the case contained an error."
            ),
            "supporting_evidence": [],
            "missing_evidence": [
                "Reliable investigation result unavailable."
            ],
            "risk_flags": [
                "INVESTIGATION_ERROR",
                str(exc),
            ],
        }


# ============================================================
# BATCH PROCESSOR
# ============================================================

def process_batch(
    cases: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Process multiple dispute cases.

    Each case is processed independently.

    One malformed case does NOT stop the remaining cases.
    """

    if not isinstance(cases, list):

        raise ValueError(
            "cases must be a list."
        )

    results = []

    for case in cases:

        result = process_case(case)

        results.append(result)

    return results


# ============================================================
# SAMPLE DATA
# ============================================================

def get_sample_cases() -> List[Dict[str, Any]]:
    """
    Return sample cases for testing the batch processor.
    """

    return [

        # ----------------------------------------------------
        # CASE 1 - STRONG EVIDENCE
        # ----------------------------------------------------

        {
            "dispute": {
                "dispute_id": "D001",
                "reason": "product_not_received",
                "amount": 8499,
                "deadline": "2026-09-02",
            },

            "order": {
                "order_id": "O001",
                "status": "delivered",
                "amount": 8499,
            },

            "payment": {
                "status": "successful",
                "amount": 8499,
            },

            "delivery": {
                "status": "delivered",
                "delivery_date": "2026-08-14",
            },

            "sessions": [
                {
                    "event": "order_page_view",
                    "timestamp": "2026-08-14T10:30:00",
                }
            ],

            "past_disputes": [],
        },


        # ----------------------------------------------------
        # CASE 2 - MISSING DELIVERY
        # ----------------------------------------------------

        {
            "dispute": {
                "dispute_id": "D002",
                "reason": "product_not_received",
                "amount": 5000,
                "deadline": "2026-09-03",
            },

            "order": {
                "order_id": "O002",
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
        },


        # ----------------------------------------------------
        # CASE 3 - CONFLICTING DELIVERY
        # ----------------------------------------------------

        {
            "dispute": {
                "dispute_id": "D003",
                "reason": "product_not_received",
                "amount": 7000,
                "deadline": "2026-09-03",
            },

            "order": {
                "order_id": "O003",
                "status": "delivered",
                "amount": 7000,
            },

            "payment": {
                "status": "successful",
                "amount": 7000,
            },

            "delivery": {
                "status": "failed",
                "delivery_date": None,
            },

            "sessions": [],

            "past_disputes": [],
        },


        # ----------------------------------------------------
        # CASE 4 - DUPLICATE CHARGE
        # ----------------------------------------------------

        {
            "dispute": {
                "dispute_id": "D004",
                "reason": "duplicate_charge",
                "amount": 3000,
                "deadline": "2026-09-04",
            },

            "order": {
                "order_id": "O004",
                "status": "completed",
                "amount": 3000,
            },

            "payment": {
                "status": "successful",
                "amount": 3000,
            },

            "delivery": {
                "status": "delivered",
                "delivery_date": "2026-08-20",
            },

            "sessions": [],

            "past_disputes": [],
        },


        # ----------------------------------------------------
        # CASE 5 - MALFORMED INPUT
        # ----------------------------------------------------

        {
            "dispute": {
                "dispute_id": "D005",
                "reason": "product_not_received",
                "amount": "hello",
            },

            "order": {
                "order_id": "O005",
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
        },
    ]


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":

    cases = get_sample_cases()

    results = process_batch(cases)

    print(
        json.dumps(
            results,
            indent=2,
        )
    )