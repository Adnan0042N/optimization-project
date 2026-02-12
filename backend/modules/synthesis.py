"""
Synthesis Question Generator — creates questions that force the learner
to COMBINE multiple prerequisites in a novel scenario.
"""

from modules.llm_client import call_llm
from modules import cache


SYNTHESIS_PROMPT = """You are an expert educator creating synthesis questions.

The student just learned these concepts:
{prerequisites}

Now they need to understand: "{concept}"

Create a synthesis question that:
1. Presents a CONCRETE, real-world scenario (2-3 sentences).
2. Requires the student to USE and COMBINE at least 2 of the prerequisites.
3. Has 2-3 numbered sub-questions that probe different angles.
4. Cannot be answered by just repeating definitions — requires REASONING.
5. Difficulty: {difficulty}

RESPOND IN THIS EXACT FORMAT:

**Scenario:**
[Your scenario here]

**Questions:**
1. [First question]
2. [Second question]
3. [Third question]

**Think through:**
- How does [prereq1] affect the outcome?
- How does [prereq2] change things?
- What happens if you change one but not the other?"""


def generate_synthesis_question(
    concept: str,
    prerequisites: list[str],
    difficulty: str = "medium",
) -> str:
    """Create a synthesis question combining the given prerequisites."""
    # Check cache
    cached = cache.get_cached_synthesis(concept, prerequisites)
    if cached:
        return cached

    if len(prerequisites) < 1:
        return _single_concept_question(concept)

    prereq_text = "\n".join(f"- {p}" for p in prerequisites)
    question = call_llm(
        SYNTHESIS_PROMPT.format(
            concept=concept,
            prerequisites=prereq_text,
            difficulty=difficulty,
        ),
        temperature=0.8,
    )

    # Cache the question
    cache.store_synthesis(concept, prerequisites, question, difficulty)
    return question


def _single_concept_question(concept: str) -> str:
    """Fallback for the very first concept (no prerequisites yet)."""
    prompt = f"""Create a simple check-understanding question for "{concept}".

The question should:
1. Present a real-world scenario (1-2 sentences)
2. Ask the student to explain what happens and WHY
3. Require more than just repeating the definition

Format:
**Scenario:** [scenario]
**Question:** [question]"""

    return call_llm(prompt, temperature=0.8)
