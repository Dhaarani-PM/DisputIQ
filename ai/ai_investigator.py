"""
DisputIQ - AI Investigator

Step 2:
LLM-powered dispute investigation.

This module:
- Accepts a structured dispute case
- Sends ONLY the provided evidence to the LLM
- Makes the investigation reason-aware
- Prevents the model from inventing evidence
- Requests structured JSON output
- Returns a consistent investigation result
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv
from openai import (
    APIConnectionError,
    AuthenticationError,
    OpenAI,
    OpenAIError,
)

from result_validator import (
    create_safe_result,
    validate_result as validate_ai_result,
)


# ============================================================
# ENVIRONMENT
# ============================================================

load_dotenv(Path(__file__).resolve().parent / ".env")

def is_placeholder_secret(value: str | None) -> bool:
    """Return True when a required secret is absent or clearly an example."""

    if not value:
        return True

    normalized = value.strip().lower()

    return normalized.startswith((
        "your_",
        "your-",
        "replace_",
        "replace-",
        "sk-your",
        "<",
    ))


def get_openai_client() -> OpenAI:
    """Create a client only after validating the configured API key."""

    api_key = os.getenv("OPENAI_API_KEY")

    if is_placeholder_secret(api_key):
        raise RuntimeError(
            "OPENAI_API_KEY is missing or still contains a placeholder. "
            "Create an API key in the OpenAI Platform and set it in .env."
        )

    return OpenAI(api_key=api_key)


# ============================================================
# SYSTEM PROMPT
# ============================================================

SYSTEM_PROMPT = """
You are the AI Investigation Engine for DisputIQ,
a chargeback investigation system.

Your job is to analyze a structured dispute case and determine
whether the available evidence supports challenging the dispute.

IMPORTANT RULES:

1. ONLY use evidence explicitly present in the input.
2. NEVER invent, assume, or fabricate evidence.
3. If evidence is missing, explicitly mention it.
4. If evidence conflicts, explicitly identify the conflict.
5. Analyze evidence according to the dispute reason.
6. Do not treat missing evidence as positive evidence.
7. Do not make the final business/legal decision.
8. Your recommendation can only be:
   - CHALLENGE
   - NEEDS_MORE_EVIDENCE
9. Evidence strength can only be:
   - HIGH
   - MEDIUM
   - LOW
   - INSUFFICIENT
10. Confidence must be a number between 0.00 and 1.00.
11. High confidence requires strong and consistent evidence.
12. Conflicting or critical missing evidence should reduce confidence.
13. Return ONLY valid JSON.
14. Keep dispute_id exactly as provided.

The output must contain exactly these fields:

{
  "dispute_id": "string",
  "evidence_strength": "HIGH | MEDIUM | LOW | INSUFFICIENT",
  "confidence": 0.00,
  "recommendation": "CHALLENGE | NEEDS_MORE_EVIDENCE",
  "reasoning": "string",
  "supporting_evidence": [],
  "missing_evidence": [],
  "risk_flags": []
}
"""


# ============================================================
# USER PROMPT BUILDER
# ============================================================

def build_investigation_prompt(case: Dict[str, Any]) -> str:
    """
    Convert the structured case into a controlled prompt.

    The complete case is serialized as JSON so the model can
    inspect the actual evidence.
    """

    return f"""
Investigate the following chargeback dispute.

Analyze the evidence according to the dispute reason.

Do NOT create evidence that is not present.

CASE:

{json.dumps(case, indent=2, default=str)}

Return ONLY the required JSON object.
"""


# ============================================================
# AI INVESTIGATION
# ============================================================

def investigate_with_ai(case: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run one structured dispute investigation through the LLM.
    """

    if not isinstance(case, dict):
        raise ValueError(
            "case must be a dictionary."
        )

    prompt = build_investigation_prompt(case)
    client = get_openai_client()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        response_format={
            "type": "json_object"
        },
        messages=[
            {
                "role": "system",
                "content": SYSTEM_PROMPT,
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
    )

    raw_content = response.choices[0].message.content

    if not raw_content:
        raise RuntimeError(
            "The AI returned an empty response."
        )

    try:
        result = json.loads(raw_content)

    except json.JSONDecodeError:
        return create_safe_result(
            case,
            "The AI returned invalid JSON.",
            ["INVALID_AI_JSON"],
        )

    # Keep direct LLM usage on the same validated result contract as the
    # rule-based and RocketRide paths.
    return validate_ai_result(result, case)


# ============================================================
# LOCAL TEST CASE
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

    try:
        result = investigate_with_ai(sample_case)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    except AuthenticationError:
        print(
            "OpenAI authentication failed. Replace OPENAI_API_KEY in .env "
            "with a valid API Platform key.",
            file=sys.stderr,
        )
        sys.exit(1)
    except APIConnectionError as exc:
        print(
            "Could not connect to the OpenAI API. Check your network connection "
            f"and try again. Details: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)
    except OpenAIError as exc:
        print(
            f"The OpenAI request failed: {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    print(
        json.dumps(
            result,
            indent=2,
        )
    )
