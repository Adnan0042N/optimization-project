"""
First-Principles Explainer — generates concept explanations
building from what the user already knows.
"""

from modules.llm_client import call_llm


EXPLAIN_PROMPT = """You are a world-class teacher who explains concepts using first principles.

Explain "{concept}" to a student.

Rules:
1. Start from the simplest truth (like explaining to a curious 12-year-old).
2. Build up step by step — each sentence should follow logically from the last.
3. Use ONE concrete, real-world example the student can visualize.
4. Maximum 5 sentences total.
5. If a prerequisite is needed, assume the student already understands: {known}
6. NO jargon unless you define it in the same sentence.
7. End with a memorable "think of it like…" analogy if possible.

Explain "{concept}":"""


def explain_concept(concept: str, known_concepts: list[str] | None = None) -> str:
    """Generate a first-principles explanation of a concept."""
    known = ", ".join(known_concepts) if known_concepts else "basic everyday experience"
    response = call_llm(
        EXPLAIN_PROMPT.format(concept=concept, known=known),
        temperature=0.7,
    )
    return response
