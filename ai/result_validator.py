"""
DisputIQ - Investigation Result Validator

Step 3:
Validate and sanitize AI investigation results.

The validator makes sure:
- Required fields exist
- Evidence strength is valid
- Recommendation is valid
- Confidence is between 0 and 1
- Lists contain strings
- dispute_id is preserved
- Missing/conflicting evidence is not silently ignored
"""

from typing import Any, Dict, List


# ============================================================
# VALID VALUES
# ============================================================

VALID_STRENGTHS = {
    "HIGH",
    "MEDIUM",
    "LOW",
    "INSUFFICIENT",
}

VALID_RECOMMENDATIONS = {
    "CHALLENGE",
    "NEEDS_MORE_EVIDENCE",
}


# ============================================================
# HELPERS
# ============================================================

def safe_string_list(value: Any) -> List[str]:
    """
    Convert a value into a safe list of strings.

    Invalid values become an empty list.
    """

    if not isinstance(value, list):
        return []

    return [
        str(item)
        for item in value
        if item is not None
    ]


# ============================================================
# VALIDATOR
# ============================================================

def validate_result(
    result: Dict[str, Any],
    original_case: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validate the AI investigation result.

    If the AI output is invalid, the validator returns a safe
    NEEDS_MORE_EVIDENCE result instead of trusting it.
    """

    # --------------------------------------------------------
    # Basic type validation
    # --------------------------------------------------------

    if not isinstance(result, dict):

        return create_safe_result(
            original_case,
            "AI returned an invalid result object.",
            ["INVALID_AI_OUTPUT"],
        )

    # --------------------------------------------------------
    # dispute_id
    # --------------------------------------------------------

    original_dispute_id = (
        original_case
        .get("dispute", {})
        .get("dispute_id")
    )

    result_dispute_id = result.get(
        "dispute_id"
    )

    # The original case ID is the source of truth.
    if result_dispute_id != original_dispute_id:

        return create_safe_result(
            original_case,
            "AI result contained an invalid dispute_id.",
            ["DISPUTE_ID_MISMATCH"],
        )

    # --------------------------------------------------------
    # Evidence strength
    # --------------------------------------------------------

    evidence_strength = result.get(
        "evidence_strength"
    )

    if evidence_strength not in VALID_STRENGTHS:

        return create_safe_result(
            original_case,
            "AI returned an invalid evidence strength.",
            ["INVALID_EVIDENCE_STRENGTH"],
        )

    # --------------------------------------------------------
    # Recommendation
    # --------------------------------------------------------

    recommendation = result.get(
        "recommendation"
    )

    if recommendation not in VALID_RECOMMENDATIONS:

        return create_safe_result(
            original_case,
            "AI returned an invalid recommendation.",
            ["INVALID_RECOMMENDATION"],
        )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    confidence = result.get(
        "confidence"
    )

    if (
        not isinstance(confidence, (int, float))
        or isinstance(confidence, bool)
    ):

        return create_safe_result(
            original_case,
            "AI returned an invalid confidence value.",
            ["INVALID_CONFIDENCE"],
        )

    if not 0.0 <= confidence <= 1.0:

        return create_safe_result(
            original_case,
            "AI confidence must be between 0 and 1.",
            ["CONFIDENCE_OUT_OF_RANGE"],
        )

    # --------------------------------------------------------
    # Reasoning
    # --------------------------------------------------------

    reasoning = result.get(
        "reasoning"
    )

    if not isinstance(reasoning, str) or not reasoning.strip():

        return create_safe_result(
            original_case,
            "AI did not provide valid reasoning.",
            ["MISSING_REASONING"],
        )

    # --------------------------------------------------------
    # Evidence arrays
    # --------------------------------------------------------

    supporting_evidence = safe_string_list(
        result.get("supporting_evidence")
    )

    missing_evidence = safe_string_list(
        result.get("missing_evidence")
    )

    risk_flags = safe_string_list(
        result.get("risk_flags")
    )

    # --------------------------------------------------------
    # Safety rule:
    # If important evidence is missing or risk exists,
    # do not allow an overconfident CHALLENGE.
    # --------------------------------------------------------

    if (
        recommendation == "CHALLENGE"
        and (
            len(missing_evidence) > 0
            or len(risk_flags) > 0
        )
    ):

        recommendation = "NEEDS_MORE_EVIDENCE"

        risk_flags.append(
            "CHALLENGE_BLOCKED_BY_MISSING_OR_RISK_EVIDENCE"
        )

        confidence = min(
            float(confidence),
            0.60,
        )

    # --------------------------------------------------------
    # Return normalized result
    # --------------------------------------------------------

    return {
        "dispute_id": original_dispute_id,
        "evidence_strength": evidence_strength,
        "confidence": round(
            float(confidence),
            2,
        ),
        "recommendation": recommendation,
        "reasoning": reasoning.strip(),
        "supporting_evidence": supporting_evidence,
        "missing_evidence": missing_evidence,
        "risk_flags": risk_flags,
    }


# ============================================================
# SAFE RESULT
# ============================================================

def create_safe_result(
    original_case: Dict[str, Any],
    reason: str,
    flags: List[str],
) -> Dict[str, Any]:
    """
    Create a safe fallback result.

    When something goes wrong, the system should prefer
    NEEDS_MORE_EVIDENCE rather than incorrectly challenging
    a dispute.
    """

    dispute_id = (
        original_case
        .get("dispute", {})
        .get("dispute_id")
    )

    return {
        "dispute_id": dispute_id,
        "evidence_strength": "INSUFFICIENT",
        "confidence": 0.0,
        "recommendation": "NEEDS_MORE_EVIDENCE",
        "reasoning": reason,
        "supporting_evidence": [],
        "missing_evidence": [
            "Reliable AI investigation result is unavailable."
        ],
        "risk_flags": flags,
    }


# ============================================================
# TEST
# ============================================================

if __name__ == "__main__":

    case = {
        "dispute": {
            "dispute_id": "D1042",
            "reason": "product_not_received",
            "amount": 8499,
        }
    }

    # Example of a valid AI result
    ai_result = {
        "dispute_id": "D1042",
        "evidence_strength": "HIGH",
        "confidence": 0.96,
        "recommendation": "CHALLENGE",
        "reasoning": (
            "Payment, order and delivery records "
            "support the merchant's case."
        ),
        "supporting_evidence": [
            "Payment successful",
            "Order amount matches payment",
            "Delivery confirmed",
        ],
        "missing_evidence": [],
        "risk_flags": [],
    }

    validated = validate_result(
        ai_result,
        case,
    )

    import json

    print(
        json.dumps(
            validated,
            indent=2,
        )
    )