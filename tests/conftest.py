"""Shared test helpers.

``ScriptedLLM`` is a stand-in for a chat model: it records the prompts it
receives and returns prepared outputs in order (raising a prepared exception
when one is supplied). Every test that exercises the AI path uses it, so tests
never touch the real API.
"""

from langchain_core.runnables import RunnableLambda


class ScriptedLLM:
    """Stand-in for a chat model: returns preset outputs in order."""

    def __init__(self, *outputs):
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    def with_structured_output(self, schema):
        def run(prompt_value):
            self.prompts.append(prompt_value.to_string())
            out = self.outputs.pop(0)
            if isinstance(out, Exception):
                raise out
            return out

        return RunnableLambda(run)
