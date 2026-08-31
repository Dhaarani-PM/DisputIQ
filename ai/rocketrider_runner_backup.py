
"""
DisputIQ - RocketRide Pipeline Runner

Runs the Chargeback Investigation pipeline through RocketRide.

Flow:

Structured Case
    ->
Build Investigation Prompt
    ->
RocketRide Pipeline
    ->
AI Investigation
    ->
Structured JSON Result
"""

import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict

from rocketride import RocketRideClient


# ============================================================
# PATH CONFIGURATION
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

PIPELINE_FILE = BASE_DIR / "chargeback_investigation.pipe"


# ============================================================
# ROCKETRIDE CONFIGURATION
# ============================================================

ROCKETRIDE_URI = os.getenv(
    "ROCKETRIDE_URI",
    "ws://localhost:5565",
)

ROCKETRIDE_APIKEY = os.getenv(
    "ROCKETRIDE_APIKEY",
    "",
)


# ============================================================
# AI SYSTEM INSTRUCTIONS
# ============================================================

SYSTEM_INSTRUCTIONS = """
You are the DisputIQ AI Investigation Engine.

Your job is to investigate a chargeback dispute using ONLY
the evidence supplied in the case.

RULES:

1. Never invent evidence.

2. Never assume missing evidence exists.

3. Missing evidence must be listed explicitly.

4. Detect contradictory evidence.

5. Add contradictory evidence to risk_flags.

6. Analyze evidence according to the dispute reason.

7. evidence_strength must be exactly one of:

HIGH
MEDIUM
LOW
INSUFFICIENT

8. confidence must be a number between 0.00 and 1.00.

9. recommendation must be exactly one of:

CHALLENGE
NEEDS_MORE_EVIDENCE

10. CHALLENGE should only be recommended when the available
evidence strongly supports the merchant.

11. If important evidence is missing, prefer
NEEDS_MORE_EVIDENCE.

12. If evidence is contradictory, prefer
NEEDS_MORE_EVIDENCE.

13. The AI is NOT the final decision maker.

14. Do not automatically submit or approve a dispute.

15. Return ONLY valid JSON.

Required JSON format:

{
  "dispute_id": "string",
  "evidence_strength": "HIGH",
  "confidence": 0.00,
  "recommendation": "CHALLENGE",
  "reasoning": "string",
  "supporting_evidence": [],
  "missing_evidence": [],
  "risk_flags": []
}
"""


# ============================================================
# BUILD PROMPT
# ============================================================

def build_question(case: Dict[str, Any]) -> str:
    """
    Convert structured dispute data into the input prompt
    sent to the RocketRide pipeline.
    """

    if not isinstance(case, dict):
        raise ValueError("case must be a dictionary")

    case_json = json.dumps(
        case,
        indent=2,
        default=str,
    )

    return (
        SYSTEM_INSTRUCTIONS
        + "\n\n"
        + "CASE TO INVESTIGATE:\n"
        + case_json
        + "\n\n"
        + "Return ONLY the JSON object."
    )


# ============================================================
# PARSE JSON RESPONSE
# ============================================================

def parse_json_text(text: str) -> Dict[str, Any]:
    """
    Convert RocketRide text response into a dictionary.
    """

    if not isinstance(text, str):
        raise RuntimeError(
            "RocketRide response is not text."
        )

    text = text.strip()

    # Handle accidental markdown JSON fences.
    if text.startswith("```json"):
        text = text[len("```json"):].strip()

    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    try:
        result = json.loads(text)

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "RocketRide returned invalid JSON.\n\n"
            + text
        ) from exc

    if not isinstance(result, dict):
        raise RuntimeError(
            "RocketRide result must be a JSON object."
        )

    return result


# ============================================================
# NORMALIZE ROCKETRIDE RESPONSE
# ============================================================

def normalize_result(
    raw_result: Any,
) -> Dict[str, Any]:
    """
    Convert different RocketRide response formats into
    a normal Python dictionary.
    """

    # Direct dictionary
    if isinstance(raw_result, dict):

        if "answer" in raw_result:

            answer = raw_result["answer"]

            if isinstance(answer, dict):
                return answer

            if isinstance(answer, str):
                return parse_json_text(answer)

        return raw_result

    # Direct string
    if isinstance(raw_result, str):
        return parse_json_text(raw_result)

    # SDK response object
    if hasattr(raw_result, "answer"):

        answer = raw_result.answer

        if isinstance(answer, dict):
            return answer

        if isinstance(answer, str):
            return parse_json_text(answer)

    # Try string representation as a final fallback.
    try:
        return parse_json_text(str(raw_result))
    except Exception as exc:

        raise RuntimeError(
            "Unable to understand RocketRide response.\n"
            f"Response type: {type(raw_result)}\n"
            f"Response: {raw_result}"
        ) from exc


# ============================================================
# VALIDATE AI RESULT
# ============================================================

def validate_result(
    result: Dict[str, Any],
    case: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Validate the structured AI investigation result.
    """

    required_fields = [
        "dispute_id",
        "evidence_strength",
        "confidence",
        "recommendation",
        "reasoning",
        "supporting_evidence",
        "missing_evidence",
        "risk_flags",
    ]

    # --------------------------------------------------------
    # Recover dispute_id if AI forgot it
    # --------------------------------------------------------

    if not result.get("dispute_id"):

        dispute = case.get(
            "dispute",
            {},
        )

        result["dispute_id"] = dispute.get(
            "dispute_id",
            "UNKNOWN",
        )

    # --------------------------------------------------------
    # Required fields
    # --------------------------------------------------------

    missing_fields = [
        field
        for field in required_fields
        if field not in result
    ]

    if missing_fields:

        raise RuntimeError(
            "AI result is missing fields: "
            + ", ".join(missing_fields)
        )

    # --------------------------------------------------------
    # Evidence strength
    # --------------------------------------------------------

    valid_strengths = {
        "HIGH",
        "MEDIUM",
        "LOW",
        "INSUFFICIENT",
    }

    if result["evidence_strength"] not in valid_strengths:

        raise RuntimeError(
            "Invalid evidence_strength: "
            + str(result["evidence_strength"])
        )

    # --------------------------------------------------------
    # Recommendation
    # --------------------------------------------------------

    valid_recommendations = {
        "CHALLENGE",
        "NEEDS_MORE_EVIDENCE",
    }

    if result["recommendation"] not in valid_recommendations:

        raise RuntimeError(
            "Invalid recommendation: "
            + str(result["recommendation"])
        )

    # --------------------------------------------------------
    # Confidence
    # --------------------------------------------------------

    try:
        confidence = float(
            result["confidence"]
        )

    except (TypeError, ValueError) as exc:

        raise RuntimeError(
            "confidence must be a number."
        ) from exc

    if not 0.0 <= confidence <= 1.0:

        raise RuntimeError(
            "confidence must be between 0.00 and 1.00."
        )

    result["confidence"] = round(
        confidence,
        2,
    )

    # --------------------------------------------------------
    # List fields
    # --------------------------------------------------------

    for field in [
        "supporting_evidence",
        "missing_evidence",
        "risk_flags",
    ]:

        if not isinstance(
            result[field],
            list,
        ):

            raise RuntimeError(
                f"{field} must be a list."
            )

    return result


# ============================================================
# ROCKETRIDE EXECUTION
# ============================================================

async def run_investigation_async(
    case: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run one dispute case through RocketRide.
    """

    # --------------------------------------------------------
    # Validate input
    # --------------------------------------------------------

    if not isinstance(case, dict):
        raise ValueError(
            "case must be a dictionary."
        )

    # --------------------------------------------------------
    # Check pipeline file
    # --------------------------------------------------------

    if not PIPELINE_FILE.exists():

        raise FileNotFoundError(
            "RocketRide pipeline file was not found:\n"
            + str(PIPELINE_FILE)
        )

    # --------------------------------------------------------
    # Create RocketRide client
    # --------------------------------------------------------

    client = RocketRideClient(
        uri=ROCKETRIDE_URI,
        auth=ROCKETRIDE_APIKEY,
    )

    try:

        print()
        print("=" * 60)
        print("Connecting to RocketRide...")
        print("=" * 60)

        # ----------------------------------------------------
        # CONNECT
        # ----------------------------------------------------

        connect_result = await client.connect()

        print("RocketRide connection successful.")

        # ----------------------------------------------------
        # LOAD PIPELINE
        # ----------------------------------------------------

        print()
        print("Loading pipeline:")
        print(PIPELINE_FILE)

        pipeline_result = await client.use(
            filepath=str(PIPELINE_FILE)
        )

        print("Pipeline loaded.")

        # ----------------------------------------------------
        # GET TOKEN
        # ----------------------------------------------------

        if isinstance(
            pipeline_result,
            dict,
        ):

            token = (
                pipeline_result.get("token")
                or pipeline_result.get("task_token")
                or pipeline_result.get("id")
            )

        else:

            token = pipeline_result

        if not token:

            raise RuntimeError(
                "RocketRide did not return a pipeline token.\n"
                f"Response: {pipeline_result}"
            )

        print(
            "Pipeline token obtained."
        )

        # ----------------------------------------------------
        # BUILD INPUT
        # ----------------------------------------------------

        question = build_question(
            case
        )

        # ----------------------------------------------------
        # RUN PIPELINE
        # ----------------------------------------------------

        print()
        print(
            "Running AI Investigation through RocketRide..."
        )

        raw_result = await client.send(
            token,
            question,
        )

        print(
            "RocketRide investigation completed."
        )

        # ----------------------------------------------------
        # NORMALIZE
        # ----------------------------------------------------

        result = normalize_result(
            raw_result
        )

        # ----------------------------------------------------
        # VALIDATE
        # ----------------------------------------------------

        result = validate_result(
            result,
            case,
        )

        return result

    finally:

        # ----------------------------------------------------
        # DISCONNECT
        # ----------------------------------------------------

        try:

            await client.disconnect()

            print(
                "RocketRide disconnected."
            )

        except Exception as exc:

            print(
                "Warning: could not disconnect cleanly:"
            )

            print(
                exc
            )


# ============================================================
# SYNCHRONOUS FUNCTION
# ============================================================

def run_investigation(
    case: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Normal Python wrapper for the async RocketRide runner.
    """

    return asyncio.run(
        run_investigation_async(
            case
        )
    )


# ============================================================
# TEST CASE
# ============================================================

if __name__ == "__main__":

    test_case = {

        "dispute": {

            "dispute_id": "RR001",

            "reason": "product_not_received",

            "amount": 8499,

            "deadline": "2026-09-02",
        },

        "order": {

            "order_id": "O-RR-001",

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

        "sessions": [],

        "past_disputes": [],
    }

    try:

        result = run_investigation(
            test_case
        )

        print()
        print("=" * 60)
        print("FINAL AI RESULT")
        print("=" * 60)

        print(
            json.dumps(
                result,
                indent=2,
                ensure_ascii=False,
            )
        )

        print()
        print("SUCCESS")

    except Exception as exc:

        print()
        print("=" * 60)
        print("ROCKETRIDE EXECUTION FAILED")
        print("=" * 60)

        print(
            f"Error type: {type(exc).__name__}"
        )

        print(
            f"Error: {exc}"
        )

        raise

