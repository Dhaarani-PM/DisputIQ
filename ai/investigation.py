"""
DisputIQ - AI Investigation Engine

Step 1:
A rule-based foundation for investigating chargeback disputes.

This module:
- Accepts structured dispute cases
- Checks evidence based on dispute reason
- Detects missing evidence
- Detects contradictory evidence
- Calculates evidence strength
- Produces a structured investigation result

IMPORTANT:
This module never invents evidence.
It only uses information present in the input case.
"""

from typing import Any, Dict, List, Optional


# ============================================================
# VALID VALUES
# ============================================================

VALID_EVIDENCE_STRENGTH = {
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
# SAFE HELPERS
# ============================================================

def is_valid_number(value: Any) -> bool:
    """
    Check whether a value is a valid numeric amount.

    Strings such as "hello" are considered invalid.
    """
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def get_nested(data: Dict[str, Any], *keys: str) -> Any:
    """
    Safely get a nested value from a dictionary.

    Example:
        get_nested(case, "dispute", "amount")

    If anything is missing, returns None instead of crashing.
    """

    current = data

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def is_available(value: Any) -> bool:
    """
    Determine whether evidence is actually available.

    None, empty strings and empty dictionaries/lists are treated
    as unavailable.
    """

    if value is None:
        return False

    if isinstance(value, str) and not value.strip():
        return False

    if isinstance(value, (list, dict)) and len(value) == 0:
        return False

    return True


# ============================================================
# INPUT VALIDATION
# ============================================================

def validate_case(case: Any) -> List[str]:
    """
    Validate the basic structure of an incoming dispute case.

    This function does not crash on malformed input.
    It returns a list of problems instead.
    """

    errors = []

    if not isinstance(case, dict):
        errors.append("Case must be a JSON object.")
        return errors

    if "dispute" not in case:
        errors.append("Missing dispute object.")

    if "order" not in case:
        errors.append("Missing order object.")

    if "payment" not in case:
        errors.append("Missing payment object.")

    return errors


# ============================================================
# DISPUTE REASON → IMPORTANT EVIDENCE
# ============================================================

def get_relevant_evidence(reason: str) -> List[str]:
    """
    Return evidence categories that are important for a
    particular dispute reason.
    """

    reason = reason.lower().strip()

    evidence_map = {
        "product_not_received": [
            "order",
            "delivery",
            "sessions",
        ],

        "item_not_received": [
            "order",
            "delivery",
            "sessions",
        ],

        "duplicate_charge": [
            "payment",
            "order",
        ],

        "fraudulent_transaction": [
            "payment",
            "sessions",
            "order",
        ],

        "unauthorized_transaction": [
            "payment",
            "sessions",
            "order",
        ],

        "subscription_cancelled": [
            "payment",
            "order",
            "sessions",
        ],

        "subscription_not_cancelled": [
            "payment",
            "order",
            "sessions",
        ],

        "credit_not_processed": [
            "payment",
            "order",
        ],

        "refund_not_received": [
            "payment",
            "order",
        ],
    }

    # If we don't recognize the reason, use general evidence.
    return evidence_map.get(
        reason,
        [
            "payment",
            "order",
            "delivery",
            "sessions",
        ],
    )


# ============================================================
# EVIDENCE AVAILABILITY
# ============================================================

def check_missing_evidence(
    case: Dict[str, Any],
    relevant_fields: List[str],
) -> List[str]:
    """
    Identify relevant evidence that is missing.
    """

    missing = []

    for field in relevant_fields:

        value = case.get(field)

        if not is_available(value):
            missing.append(
                f"{field} evidence is unavailable."
            )

    return missing


# ============================================================
# PAYMENT / ORDER CONSISTENCY
# ============================================================

def check_payment_order_consistency(
    case: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare payment and order information.

    Returns:
        {
            "status": "MATCH" / "CONFLICT" / "UNAVAILABLE",
            "message": "..."
        }
    """

    payment_amount = get_nested(
        case,
        "payment",
        "amount",
    )

    order_amount = get_nested(
        case,
        "order",
        "amount",
    )

    if not is_valid_number(payment_amount):
        return {
            "status": "UNAVAILABLE",
            "message": "Payment amount is missing or invalid.",
        }

    if not is_valid_number(order_amount):
        return {
            "status": "UNAVAILABLE",
            "message": "Order amount is missing or invalid.",
        }

    if payment_amount == order_amount:
        return {
            "status": "MATCH",
            "message": "Payment amount matches order amount.",
        }

    return {
        "status": "CONFLICT",
        "message": (
            f"Payment amount ({payment_amount}) does not match "
            f"order amount ({order_amount})."
        ),
    }


# ============================================================
# DELIVERY / ORDER CONSISTENCY
# ============================================================

def check_delivery_consistency(
    case: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Compare order status and delivery status.
    """

    order_status = get_nested(
        case,
        "order",
        "status",
    )

    delivery_status = get_nested(
        case,
        "delivery",
        "status",
    )

    if not order_status or not delivery_status:
        return {
            "status": "UNAVAILABLE",
            "message": "Order or delivery status is unavailable.",
        }

    order_status = str(order_status).lower().strip()
    delivery_status = str(delivery_status).lower().strip()

    # Consistent delivered state
    if (
        order_status == "delivered"
        and delivery_status == "delivered"
    ):
        return {
            "status": "MATCH",
            "message": "Order and delivery records confirm delivery.",
        }

    # Clear contradiction
    if (
        order_status == "delivered"
        and delivery_status in {
            "failed",
            "cancelled",
            "returned",
            "not_delivered",
        }
    ):
        return {
            "status": "CONFLICT",
            "message": (
                "Order indicates delivery, but delivery records "
                f"show '{delivery_status}'."
            ),
        }

    return {
        "status": "NEUTRAL",
        "message": (
            f"Order status is '{order_status}' and delivery status "
            f"is '{delivery_status}'."
        ),
    }


# ============================================================
# MAIN INVESTIGATION
# ============================================================

def investigate(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main AI investigation function.

    Input:
        Structured dispute case.

    Output:
        Structured investigation result.
    """

    # --------------------------------------------------------
    # 1. Validate input
    # --------------------------------------------------------

    validation_errors = validate_case(case)

    if validation_errors:

        dispute_id = get_nested(
            case,
            "dispute",
            "dispute_id",
        )

        return {
            "dispute_id": dispute_id,
            "evidence_strength": "INSUFFICIENT",
            "confidence": 0.0,
            "recommendation": "NEEDS_MORE_EVIDENCE",
            "reasoning": (
                "The case could not be reliably investigated "
                "because required data is missing or malformed."
            ),
            "supporting_evidence": [],
            "missing_evidence": validation_errors,
            "risk_flags": [
                "MALFORMED_INPUT",
            ],
        }

    # --------------------------------------------------------
    # 2. Extract basic information
    # --------------------------------------------------------

    dispute_id = get_nested(
        case,
        "dispute",
        "dispute_id",
    )

    reason = get_nested(
        case,
        "dispute",
        "reason",
    )

    amount = get_nested(
        case,
        "dispute",
        "amount",
    )

    # --------------------------------------------------------
    # 3. Handle invalid dispute reason
    # --------------------------------------------------------

    if not isinstance(reason, str) or not reason.strip():

        return {
            "dispute_id": dispute_id,
            "evidence_strength": "INSUFFICIENT",
            "confidence": 0.0,
            "recommendation": "NEEDS_MORE_EVIDENCE",
            "reasoning": (
                "The dispute reason is missing or invalid, "
                "so the system cannot determine which evidence "
                "should receive priority."
            ),
            "supporting_evidence": [],
            "missing_evidence": [
                "Valid dispute reason is required."
            ],
            "risk_flags": [
                "INVALID_DISPUTE_REASON",
            ],
        }

    reason = reason.lower().strip()

    # --------------------------------------------------------
    # 4. Determine relevant evidence
    # --------------------------------------------------------

    relevant_fields = get_relevant_evidence(reason)

    # --------------------------------------------------------
    # 5. Detect missing evidence
    # --------------------------------------------------------

    missing_evidence = check_missing_evidence(
        case,
        relevant_fields,
    )

    # --------------------------------------------------------
    # 6. Evidence collection
    # --------------------------------------------------------

    supporting_evidence: List[str] = []
    risk_flags: List[str] = []

    # --------------------------------------------------------
    # Payment evidence
    # --------------------------------------------------------

    payment_status = get_nested(
        case,
        "payment",
        "status",
    )

    if payment_status:

        payment_status = str(payment_status).lower().strip()

        if payment_status in {
            "successful",
            "succeeded",
            "paid",
            "completed",
        }:

            supporting_evidence.append(
                "Payment record shows a successful payment."
            )

        elif payment_status in {
            "failed",
            "cancelled",
            "declined",
        }:

            risk_flags.append(
                "PAYMENT_STATUS_CONFLICT"
            )

    # --------------------------------------------------------
    # Payment / order amount
    # --------------------------------------------------------

    amount_check = check_payment_order_consistency(case)

    if amount_check["status"] == "MATCH":

        supporting_evidence.append(
            amount_check["message"]
        )

    elif amount_check["status"] == "CONFLICT":

        risk_flags.append(
            "PAYMENT_ORDER_AMOUNT_MISMATCH"
        )

    # --------------------------------------------------------
    # Order evidence
    # --------------------------------------------------------

    order_status = get_nested(
        case,
        "order",
        "status",
    )

    if order_status:

        order_status = str(order_status).lower().strip()

        if order_status == "delivered":

            supporting_evidence.append(
                "Order record indicates the order was delivered."
            )

    # --------------------------------------------------------
    # Delivery evidence
    # --------------------------------------------------------

    delivery_status = get_nested(
        case,
        "delivery",
        "status",
    )

    if delivery_status:

        delivery_status = (
            str(delivery_status)
            .lower()
            .strip()
        )

        if delivery_status == "delivered":

            supporting_evidence.append(
                "Delivery record confirms successful delivery."
            )

        elif delivery_status in {
            "failed",
            "cancelled",
            "returned",
            "not_delivered",
        }:

            risk_flags.append(
                "DELIVERY_PROBLEM"
            )

    # --------------------------------------------------------
    # Delivery / order conflict
    # --------------------------------------------------------

    delivery_check = check_delivery_consistency(case)

    if delivery_check["status"] == "CONFLICT":

        risk_flags.append(
            "ORDER_DELIVERY_CONFLICT"
        )

    # --------------------------------------------------------
    # Session evidence
    # --------------------------------------------------------

    sessions = case.get("sessions")

    if is_available(sessions):

        supporting_evidence.append(
            "Relevant customer session activity is available."
        )

    # --------------------------------------------------------
    # Past disputes
    # --------------------------------------------------------

    past_disputes = case.get("past_disputes")

    if is_available(past_disputes):

        supporting_evidence.append(
            "Historical dispute outcomes are available."
        )

    # --------------------------------------------------------
    # 7. Determine strength
    # --------------------------------------------------------

    conflict_count = len(risk_flags)

    missing_count = len(missing_evidence)

    supporting_count = len(supporting_evidence)

    # Serious conflict → cannot confidently challenge
    if conflict_count > 0:

        evidence_strength = "LOW"
        recommendation = "NEEDS_MORE_EVIDENCE"

        confidence = 0.35

    # Important evidence missing
    elif missing_count >= 2:

        evidence_strength = "LOW"
        recommendation = "NEEDS_MORE_EVIDENCE"

        confidence = 0.40

    elif missing_count == 1:

        evidence_strength = "MEDIUM"
        recommendation = "NEEDS_MORE_EVIDENCE"

        confidence = 0.60

    # Strong evidence
    elif supporting_count >= 3:

        evidence_strength = "HIGH"
        recommendation = "CHALLENGE"

        confidence = 0.90

    # Some evidence
    elif supporting_count >= 1:

        evidence_strength = "MEDIUM"
        recommendation = "NEEDS_MORE_EVIDENCE"

        confidence = 0.65

    # Almost nothing available
    else:

        evidence_strength = "INSUFFICIENT"
        recommendation = "NEEDS_MORE_EVIDENCE"

        confidence = 0.20

    # --------------------------------------------------------
    # 8. Special handling for product-not-received
    # --------------------------------------------------------

    if reason in {
        "product_not_received",
        "item_not_received",
    }:

        if (
            order_status == "delivered"
            and delivery_status == "delivered"
            and "ORDER_DELIVERY_CONFLICT" not in risk_flags
        ):

            if not missing_evidence:

                evidence_strength = "HIGH"
                recommendation = "CHALLENGE"
                confidence = 0.95

        elif (
            delivery_status in {
                "failed",
                "cancelled",
                "returned",
                "not_delivered",
            }
        ):

            evidence_strength = "LOW"
            recommendation = "NEEDS_MORE_EVIDENCE"
            confidence = 0.30

    # --------------------------------------------------------
    # 9. Special handling for duplicate charge
    # --------------------------------------------------------

    if reason == "duplicate_charge":

        payment_amount = get_nested(
            case,
            "payment",
            "amount",
        )

        order_amount = get_nested(
            case,
            "order",
            "amount",
        )

        if (
            is_valid_number(payment_amount)
            and is_valid_number(order_amount)
            and payment_amount == order_amount
        ):

            # Matching payment/order does NOT prove
            # a duplicate charge by itself.
            evidence_strength = "MEDIUM"
            recommendation = "NEEDS_MORE_EVIDENCE"
            confidence = 0.60

            supporting_evidence.append(
                "Payment and order amounts are consistent, "
                "but duplicate transaction evidence is required."
            )

            if "Duplicate transaction records are unavailable." not in missing_evidence:

                missing_evidence.append(
                    "Duplicate transaction records are unavailable."
                )

    # --------------------------------------------------------
    # 10. Build reasoning
    # --------------------------------------------------------

    if recommendation == "CHALLENGE":

        reasoning = (
            f"The available evidence supports challenging the "
            f"'{reason}' dispute. "
            f"{' '.join(supporting_evidence[:4])}"
        )

    else:

        if risk_flags:

            reasoning = (
                f"The '{reason}' dispute cannot be confidently "
                f"challenged because potentially conflicting or "
                f"risky evidence was detected."
            )

        elif missing_evidence:

            reasoning = (
                f"The '{reason}' dispute cannot be confidently "
                f"challenged because important evidence is missing."
            )

        else:

            reasoning = (
                f"The available evidence is not strong enough "
                f"to confidently recommend challenging the "
                f"'{reason}' dispute."
            )

    # --------------------------------------------------------
    # 11. Return structured result
    # --------------------------------------------------------

    return {
        "dispute_id": dispute_id,
        "evidence_strength": evidence_strength,
        "confidence": round(confidence, 2),
        "recommendation": recommendation,
        "reasoning": reasoning,
        "supporting_evidence": supporting_evidence,
        "missing_evidence": missing_evidence,
        "risk_flags": risk_flags,
    }


# ============================================================
# TEST CASE
# ============================================================

if __name__ == "__main__":

    sample_case = {
        "dispute": {
            "dispute_id": "D1042",
            "reason": "product_not_received",
            "amount": 8499,
            "deadline": "2026-09-02",
        },

        "order": {
            "order_id": "O5512",
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
    }

    result = investigate(sample_case)

    import json

    print(
        json.dumps(
            result,
            indent=2
        )
    )