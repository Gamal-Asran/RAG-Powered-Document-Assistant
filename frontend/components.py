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
          <a href="{url}" target="_blank" rel="noopener noreferrer">Open source</a>
          <div class="source-chunk">Chunk: {chunk_id}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sources(sources: list[Source]) -> None:
    unique_sources = prepare_sources(sources)
    with st.expander(f"Sources ({len(unique_sources)})", expanded=False):
        if not unique_sources:
            st.caption("No sources were returned.")
        for source in unique_sources:
            _source_card(source)


def render_thinking(message: Message) -> None:
    if not message.thinking_requested:
        return
    thinking = message.thinking.strip()
    if not thinking:
        st.caption("Thinking · No separate thinking trace was returned.")
        return
    preview = thinking[:200].rstrip() + ("…" if len(thinking) > 200 else "")
    st.markdown(
        f'<div class="thinking-preview"><strong>Thinking</strong><br>{html.escape(preview)}</div>',
        unsafe_allow_html=True,
    )
    with st.expander("Show full thinking", expanded=False):
        st.markdown(
            f'<div class="thinking-full">{html.escape(thinking).replace(chr(10), "<br>")}</div>',
            unsafe_allow_html=True,
        )


def render_message(message: Message) -> None:
    with st.chat_message(message.role):
        st.markdown(message.content)
        if message.role == "assistant":
            render_thinking(message)
            render_sources(message.sources)
            if message.retrieval_seconds is not None and message.generation_seconds is not None:
                st.caption(
                    f"Retrieved in {message.retrieval_seconds:.2f}s · "
                    f"Generated in {message.generation_seconds:.2f}s"
                )
