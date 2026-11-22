"""Streamlit demo for the notice summarizer.

Thin on purpose: every piece of logic lives in ``notice_tool``. Run with:

    streamlit run app.py
"""

from __future__ import annotations

import os

import streamlit as st
from dotenv import load_dotenv

from notice_tool.ingest import UploadError, ingest_bytes
from notice_tool.pipeline import InvalidNoticeError, apply_override, run_pipeline

_STATUS_LABEL = {"ok": "OK", "weak": "WEAK", "missing": "MISSING"}


def get_llm():
    """Return a chat model, or ``None`` when no real API key is configured."""
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key or api_key.startswith("sk-your"):
        return None

    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        api_key=api_key,
        base_url=os.getenv("OPENAI_BASE_URL") or None,
    )


def _resolve_source(notice_text: str, uploaded) -> str:
    if uploaded is not None:
        return ingest_bytes(uploaded.name, uploaded.getvalue())
    return notice_text


def _render_checklist(result) -> None:
    st.subheader("Checklist")
    for check in result.checklist:
        label = _STATUS_LABEL.get(check.status, check.status)
        st.write(f"{label} - {check.name}")
        if check.suggestion:
            st.caption(check.suggestion)


def _render_summaries(result) -> None:
    left, right = st.columns(2)
    with left:
        st.subheader("Extractive baseline")
        st.write(result.baseline.summary or "(empty)")
        st.caption(
            f"{result.baseline.original_words} words in, "
            f"{result.baseline.summary_words} out "
            f"({result.baseline.reduction:.0%} shorter)"
        )
    with right:
        st.subheader("AI summary")
        if result.ai_summary is not None:
            st.write(result.summary)
        else:
            st.info(f"No AI summary (status: {result.status}). Showing the baseline instead.")


def _render_validator(result) -> None:
    st.subheader("Validator")
    for check in result.validation.checks:
        mark = "PASS" if check.passed else "FAIL"
        st.write(f"{mark} - {check.name}: {check.detail}")


def _render_editor(result) -> None:
    st.subheader("Your version")
    edited = st.text_area(
        "Edit the final text", value=result.summary, key="final_text", height=160
    )
    if st.button("Use my edited version"):
        st.session_state.result = apply_override(result, result.source, edited)
        st.rerun()


def main() -> None:
    st.set_page_config(page_title="Notice Summarizer", layout="wide")
    st.title("School Notice Summarizer")
    st.caption("Summarise a school notice for parents, with a fact check.")

    if "result" not in st.session_state:
        st.session_state.result = None

    notice = st.text_area("Paste the notice", key="notice", height=200)
    uploaded = st.file_uploader("Or upload a .txt or .md file", type=["txt", "md"], key="upload")

    if st.button("Summarise", type="primary"):
        try:
            source = _resolve_source(notice, uploaded)
            st.session_state.result = run_pipeline(get_llm(), source)
        except (InvalidNoticeError, UploadError) as exc:
            st.session_state.result = None
            st.error(str(exc))

    result = st.session_state.result
    if result is not None:
        if result.overridden:
            st.success("Showing your edited version.")
        _render_checklist(result)
        _render_summaries(result)
        _render_validator(result)
        _render_editor(result)


main()
