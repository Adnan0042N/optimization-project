"""
Answer Validator — checks whether the user's synthesis answer demonstrates
genuine INTEGRATION of prerequisites (not just correctness).
"""

from modules.llm_client import call_llm


VALIDATE_PROMPT = """You are evaluating a student's answer to a synthesis question.

**Synthesis Question:**
{question}

**Student's Answer:**
{answer}

**Prerequisites they should integrate:**
{prerequisites}

**Evaluate using these criteria (score each 0-100):**
1. COVERAGE — Did they mention/use ALL listed prerequisites? (not just one)
2. INTEGRATION — Did they explain HOW the prerequisites relate/interact?
3. REASONING — Did they provide logical reasoning, not just facts?
4. DEPTH — Did they address nuances, edge cases, or "what if" scenarios?

**RESPOND IN THIS EXACT FORMAT (no extra text):**
SCORE: [0-100 overall score]
VERDICT: [PASS if score >= 60, otherwise FAIL]
FEEDBACK: [2-3 sentences: what they did well + what they missed]
MISSING: [comma-separated list of connections they didn't make, or "none"]
INSIGHT: [one key insight the student demonstrated, or "none"]"""


HINT_PROMPT = """A student is struggling with a synthesis question.

They missed these connections: {missing}
The prerequisites involved are: {prerequisites}

Generate a helpful HINT (NOT the answer) that nudges them toward the connection.
The hint should:
1. Ask a guiding sub-question
2. Reference a specific prerequisite they should think about
3. Be 1-2 sentences max

Hint:"""


FOLLOWUP_PROMPT = """A student struggled to connect: {missing}

Create a SIMPLER synthesis question about "{concept}" that specifically targets the relationship between {prereqs}.

The question should:
1. Be more direct and concrete than before
2. Focus on exactly ONE relationship they missed
3. Have an obvious answer if they understand the connection

Format:
**Scenario:** [simple scenario]
**Question:** [direct question about the missed connection]"""


def validate_answer(
    question: str,
    answer: str,
    prerequisites: list[str],
) -> dict:
    """
    Validate a synthesis answer for integration, not just correctness.

    Returns:
        {
            "passed": bool,
            "score": int (0-100),
            "feedback": str,
            "missing": list[str],
            "insight": str,
        }
    """
    prereq_text = ", ".join(prerequisites)
    response = call_llm(
        VALIDATE_PROMPT.format(
            question=question,
            answer=answer,
            prerequisites=prereq_text,
        ),
        temperature=0.3,
    )

    return _parse_validation(response)


def generate_hint(missing: list[str], prerequisites: list[str]) -> str:
    """Generate a targeted hint based on missed connections."""
    return call_llm(
        HINT_PROMPT.format(
            missing=", ".join(missing),
            prerequisites=", ".join(prerequisites),
        ),
        temperature=0.7,
    )


def generate_followup(
    concept: str,
    prerequisites: list[str],
    missing: list[str],
) -> str:
    """Generate a simpler followup question targeting missed connections."""
    return call_llm(
        FOLLOWUP_PROMPT.format(
            concept=concept,
            missing=", ".join(missing),
            prereqs=" and ".join(prerequisites[:2]),
        ),
        temperature=0.7,
    )


def _parse_validation(response: str) -> dict:
    """Parse the structured LLM validation response."""
    result = {
        "passed": False,
        "score": 0,
        "feedback": "",
        "missing": [],
        "insight": "",
    }

    for line in response.strip().split("\n"):
        line = line.strip()
        if line.upper().startswith("SCORE:"):
            try:
                score_str = line.split(":", 1)[1].strip()
                result["score"] = int("".join(c for c in score_str if c.isdigit())[:3])
            except (ValueError, IndexError):
                result["score"] = 50
        elif line.upper().startswith("VERDICT:"):
            verdict = line.split(":", 1)[1].strip().upper()
            result["passed"] = "PASS" in verdict
        elif line.upper().startswith("FEEDBACK:"):
            result["feedback"] = line.split(":", 1)[1].strip()
        elif line.upper().startswith("MISSING:"):
            missing_str = line.split(":", 1)[1].strip()
            if missing_str.lower() != "none":
                result["missing"] = [m.strip() for m in missing_str.split(",") if m.strip()]
        elif line.upper().startswith("INSIGHT:"):
            insight = line.split(":", 1)[1].strip()
            if insight.lower() != "none":
                result["insight"] = insight

    # Fallback: if score >= 60 but verdict wasn't parsed
    if result["score"] >= 60 and not result["passed"]:
        result["passed"] = True

    return result
