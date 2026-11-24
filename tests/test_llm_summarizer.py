"""Tests for notice_tool.llm_summarizer.

These tests never touch the real API. A tiny fake LLM stands in for the model:
it records the prompt it is given and returns a pre-built ``ParentSummary``.
"""

from langchain_core.runnables import RunnableLambda

from notice_tool.llm_summarizer import (
    ActionItem,
    KeyDate,
    ParentSummary,
    PROMPT,
    build_chain,
    summarize,
)

NOTICE = (
    "Dear Parents. The PTA meeting holds on Tuesday, 8 December 2026 at "
    "10:00 a.m. Please bring your receipt booklet. Call 0803 123 4567."
)

SAMPLE_OUTPUT = ParentSummary(
    headline="PTA meeting",
    summary="PTA meeting on 8 December 2026 at 10:00 a.m. Bring your receipt booklet.",
    key_dates=[KeyDate(what="PTA meeting", when="8 December 2026 at 10:00 a.m.")],
    actions=[ActionItem(action="Bring your receipt booklet", evidence="bring your receipt booklet")],
)


class FakeLLM:
    """Stand-in for a chat model that supports structured output."""

    def __init__(self, output):
        self.output = output
        self.prompts: list[str] = []
        self.schema = None

    def with_structured_output(self, schema):
        self.schema = schema

        def run(prompt_value):
            self.prompts.append(prompt_value.to_string())
            return self.output

        return RunnableLambda(run)


def test_structured_schema_is_requested():
    llm = FakeLLM(SAMPLE_OUTPUT)
    build_chain(llm)
    assert llm.schema is ParentSummary


def test_summarize_returns_structured_output():
    llm = FakeLLM(SAMPLE_OUTPUT)
    result = summarize(llm, NOTICE)
    assert result is SAMPLE_OUTPUT


def test_prompt_contains_the_notice():
    llm = FakeLLM(SAMPLE_OUTPUT)
    summarize(llm, NOTICE)
    assert "PTA meeting holds on Tuesday" in llm.prompts[0]


def test_prompt_states_the_key_rules():
    llm = FakeLLM(SAMPLE_OUTPUT)
    summarize(llm, NOTICE)
    prompt = llm.prompts[0]
    assert "exactly as written" in prompt
    assert "Add nothing" in prompt
    assert "prohibition" in prompt
    assert "evidence" in prompt


def test_retry_feedback_appears_in_the_prompt():
    llm = FakeLLM(SAMPLE_OUTPUT)
    summarize(llm, NOTICE, feedback="dates_preserved: missing dates: (12, 3)")
    assert "dates_preserved" in llm.prompts[0]


def test_no_feedback_leaves_no_retry_wording():
    llm = FakeLLM(SAMPLE_OUTPUT)
    summarize(llm, NOTICE)
    assert "rejected" not in llm.prompts[0]


def test_prompt_is_a_chat_prompt_template():
    # PROMPT must be chainable with a chat model via the | operator.
    assert hasattr(PROMPT, "format_messages")
