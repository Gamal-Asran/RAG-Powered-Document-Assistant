"""Reusable Streamlit rendering helpers."""

from __future__ import annotations

import html

import streamlit as st

try:
    from .models import Message, Source, prepare_sources
except ImportError:  # pragma: no cover
    from models import Message, Source, prepare_sources


def _source_card(source: Source) -> None:
    title = html.escape(source.title)
    preview = html.escape(source.text_preview.strip())
    chunk_id = html.escape(source.chunk_id)
    url = html.escape(source.url, quote=True)
    st.markdown(
        f"""
        <div class="source-card">
          <div class="source-title">{title}</div>
          <div class="source-meta">Page {source.page} · Similarity {source.similarity:.3f}</div>
          <div class="source-preview">“{preview}”</div>
          <div class="source-footer">
            <a href="{url}" target="_blank" rel="noopener noreferrer">Open document ↗</a>
            <span class="source-chunk">{chunk_id}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sources(sources: list[Source]) -> None:
    unique_sources = prepare_sources(sources)
    with st.expander(f"Sources · {len(unique_sources)}", expanded=False):
        if not unique_sources:
            st.caption("No sources were returned.")
        for source in unique_sources:
            _source_card(source)


def render_thinking(message: Message) -> None:
    if not message.thinking_requested:
        return
    thinking = message.thinking.strip()
    if not thinking:
        st.markdown('<div class="thinking-unavailable">Thinking trace unavailable</div>', unsafe_allow_html=True)
        return
    first_paragraph = thinking.split("\n\n", 1)[0].strip()
    preview = first_paragraph[:320] + ("…" if len(first_paragraph) > 320 else "")
    st.markdown(
        '<div class="thinking-preview">'
        '<div class="thinking-label"><span aria-hidden="true">▸</span> Thinking</div>'
        f'<div class="thinking-copy">{html.escape(preview)}</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.expander("View full thinking", expanded=False):
        st.markdown(thinking)


def render_message(message: Message) -> None:
    with st.chat_message(message.role):
        if message.role == "assistant":
            st.markdown(
                '<div class="assistant-label"><span aria-hidden="true">◆</span> Assistant</div>',
                unsafe_allow_html=True,
            )
        st.markdown(message.content)
        if message.role == "assistant":
            render_thinking(message)
            render_sources(message.sources)
            if message.retrieval_seconds is not None and message.generation_seconds is not None:
                st.caption(
                    f"Retrieved in {message.retrieval_seconds:.2f}s · "
                    f"Generated in {message.generation_seconds:.2f}s"
                )
