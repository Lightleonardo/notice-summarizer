"""Turn a notice into a parent-friendly summary with a large language model.

The model is forced into a structured shape (:class:`ParentSummary`) so every
piece is checkable: the headline and summary, the key dates (what + when), and
the actions (what to do + the exact words that support it). The
:mod:`notice_tool.validator` can then compare those pieces against the notice.

The prompt is the important part. Its rules are deliberate: keep facts exactly
as written, keep prohibitions, invent nothing, quote your evidence, and stay
short. On a retry we paste the validator's failure message into the prompt.

Privacy note: only send approved, synthetic, or anonymised text to a
third-party API. Real notices can contain personal details.
"""

from __future__ import annotations

from typing import Any

from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, Field


# --------------------------------------------------------------------------- #
# Structured output schema
# --------------------------------------------------------------------------- #
class KeyDate(BaseModel):
    """A date or time the parent must remember, and what it is for."""

    what: str = Field(description="What happens then, e.g. 'PTA meeting'")
    when: str = Field(description="The date/time, copied exactly from the notice")


class ActionItem(BaseModel):
    """Something the parent must do, plus the words from the notice that support it."""

    action: str = Field(description="What the parent must do")
    evidence: str = Field(
        description="Exact words copied from the notice that support this action"
    )


class ParentSummary(BaseModel):
    """The full structured summary returned by the model."""

    headline: str = Field(description="A short headline for the notice")
    summary: str = Field(description="A short plain-language summary for parents")
    key_dates: list[KeyDate] = Field(
        default_factory=list, description="Every important date/time in the notice"
    )
    actions: list[ActionItem] = Field(
        default_factory=list, description="Everything the parent must do"
    )


# --------------------------------------------------------------------------- #
# Prompt
# --------------------------------------------------------------------------- #
SYSTEM_RULES = """\
You summarise school notices for busy parents. Follow these rules exactly:

1. Keep every date, time, amount, phone number, and email exactly as written.
   Do not change, round, or reformat them.
2. Keep every prohibition: if the notice forbids something, your summary must
   say so, using a clear negation such as "must not" or "no".
3. Add nothing that is not in the notice. Never invent a date, time, amount,
   contact, or instruction.
4. For every action, copy the supporting words from the notice into the
   evidence field. The evidence must appear word-for-word in the notice.
5. Write for parents, in plain language, and be much shorter than the notice.
"""

HUMAN_TEMPLATE = """\
Here is the school notice to summarise:

<notice>
{notice}
</notice>

{feedback}"""

PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_RULES),
        ("human", HUMAN_TEMPLATE),
    ]
)


def _feedback_block(feedback: str | None) -> str:
    """Render the retry instructions, or nothing when there is no feedback."""
    if not feedback:
        return ""
    return (
        "IMPORTANT: your previous summary was rejected by our checker. "
        "Fix these problems and try again:\n"
        f"{feedback}"
    )


def build_chain(llm: Any):
    """Build the summarisation chain: prompt -> model -> structured output."""
    return PROMPT | llm.with_structured_output(ParentSummary)


def summarize(llm: Any, notice: str, *, feedback: str | None = None) -> ParentSummary:
    """Summarise ``notice`` into a :class:`ParentSummary`.

    Pass ``feedback`` (the validator's failure message) to retry after a failed
    attempt; it is appended to the prompt.
    """
    chain = build_chain(llm)
    return chain.invoke({"notice": notice, "feedback": _feedback_block(feedback)})
