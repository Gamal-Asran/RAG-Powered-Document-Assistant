"""Streamlit UI for the local NIST AI Risk RAG prototype."""

from __future__ import annotations

import html
import os
from pathlib import Path
from time import monotonic

import streamlit as st
from dotenv import load_dotenv

try:  # Support execution from the repository root and from frontend/.
    from .api_client import (
        BackendClient,
        BackendGenerationError,
        BackendRequestError,
        BackendTimeoutError,
        BackendUnavailableError,
        BackendValidationError,
        ConversationNotFoundError,
    )
    from .components import render_message, render_sources
    from .models import (
        AnswerDeltaEvent,
        CompletedEvent,
        Message,
        SourcesEvent,
        StatusEvent,
        StreamEvent,
        ThinkingDeltaEvent,
    )
    from .styles import theme_css
    from .waiting import WaitingStatus, pump_stream
except ImportError:  # pragma: no cover - Streamlit executes this file as a script
    from api_client import (
        BackendClient,
        BackendGenerationError,
        BackendRequestError,
        BackendTimeoutError,
        BackendUnavailableError,
        BackendValidationError,
        ConversationNotFoundError,
    )
    from components import render_message, render_sources
    from models import (
        AnswerDeltaEvent,
        CompletedEvent,
        Message,
        SourcesEvent,
        StatusEvent,
        StreamEvent,
        ThinkingDeltaEvent,
    )
    from styles import theme_css
    from waiting import WaitingStatus, pump_stream


FRONTEND_DIR = Path(__file__).resolve().parent
load_dotenv(FRONTEND_DIR / ".env")

st.set_page_config(
    page_title="NIST AI Risk Assistant",
    page_icon="🛡️",
    layout="wide",
)

EXAMPLE_QUESTIONS = (
    ("Framework", "What are the four core AI RMF functions?"),
    ("Generative AI", "What major risks does the GenAI Profile identify?"),
    ("Governance", "How does the Playbook support the GOVERN function?"),
    ("Trustworthiness", "What characteristics define trustworthy AI?"),
)


def initialize_state() -> None:
    defaults = {
        "active_conversation_id": None,
        "messages": [],
        "thinking_enabled": False,
        "backend_available": False,
        "conversations": [],
        "request_in_progress": False,
        "last_error": None,
        "question_draft": "",
        "clear_question_input": False,
        "restore_question_input": None,
        "pending_delete_id": None,
        "queued_question": None,
        "pending_question": None,
        "pending_thinking": False,
        "appearance": "Light",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.restore_question_input is not None:
        st.session_state.question_draft = st.session_state.restore_question_input
        st.session_state.restore_question_input = None
        st.session_state.clear_question_input = False
    elif st.session_state.clear_question_input:
        st.session_state.question_draft = ""
        st.session_state.clear_question_input = False


initialize_state()
client = BackendClient(
    os.getenv("API_BASE_URL", "http://127.0.0.1:8000"),
    query_timeout=float(os.getenv("QUERY_TIMEOUT_SECONDS", "300")),
)


def reset_for_missing_conversation() -> None:
    st.session_state.active_conversation_id = None
    st.session_state.messages = []
    st.session_state.last_error = (
        "This conversation is no longer available because backend memory was reset."
    )


def refresh_conversations() -> None:
    try:
        conversations = sorted(
            client.list_conversations(), key=lambda item: item.updated_at, reverse=True
        )
        st.session_state.conversations = conversations
        active_id = st.session_state.active_conversation_id
        if active_id and st.session_state.messages and all(item.id != active_id for item in conversations):
            reset_for_missing_conversation()
    except BackendUnavailableError:
        st.session_state.backend_available = False
    except (BackendTimeoutError, BackendValidationError, BackendRequestError):
        # Health and query errors are surfaced in the main area; sidebar refresh is best effort.
        pass


def load_conversation(conversation_id: str) -> None:
    try:
        conversation = client.get_conversation(conversation_id)
        st.session_state.active_conversation_id = conversation.id
        st.session_state.messages = [item.for_display() for item in conversation.messages]
        st.session_state.last_error = None
    except ConversationNotFoundError:
        reset_for_missing_conversation()
    except BackendUnavailableError:
        st.session_state.backend_available = False
        st.session_state.last_error = (
            "The local backend is not running. Start it on port 8000 and try again."
        )
    except (BackendTimeoutError, BackendValidationError, BackendRequestError):
        st.session_state.last_error = "The request failed. Check the backend terminal for details."


def new_chat() -> None:
    st.session_state.active_conversation_id = None
    st.session_state.messages = []
    st.session_state.last_error = None
    st.session_state.pending_delete_id = None
    st.session_state.queued_question = None


def working_markup(status: WaitingStatus) -> str:
    return (
        '<div class="working-title"><span class="working-dot" aria-hidden="true"></span>'
        f"{status.message} <span class=\"working-elapsed\">· {status.elapsed_text}</span></div>"
    )


def choose_example(question: str) -> None:
    st.session_state.queued_question = question


def friendly_query_error(error: Exception) -> str:
    if isinstance(error, BackendUnavailableError):
        st.session_state.backend_available = False
        return "The local backend is not running. Start it on port 8000 and try again."
    if isinstance(error, BackendTimeoutError):
        return "The local model took too long to respond. Try again with thinking mode disabled."
    if isinstance(error, ConversationNotFoundError):
        reset_for_missing_conversation()
        return "This conversation is no longer available because backend memory was reset."
    if isinstance(error, BackendGenerationError):
        if "ollama" in str(error).lower() or "qwen3:4b" in str(error).lower():
            return "Ollama or qwen3:4b is unavailable. Check the backend health status."
        return "The local model could not finish the response. Try again without thinking mode."
    return "The request failed. Check the backend terminal for details."


def check_health() -> None:
    try:
        health = client.health()
        st.session_state.backend_available = True
        st.session_state.health = health
    except (BackendUnavailableError, BackendTimeoutError, BackendValidationError, BackendRequestError):
        st.session_state.backend_available = False
        st.session_state.health = None


check_health()
if st.session_state.backend_available:
    refresh_conversations()


with st.sidebar:
    st.markdown(
        '<div class="sidebar-brand">'
        '<div class="sidebar-title">NIST AI Risk</div>'
        '<div class="sidebar-subtitle">Local document assistant</div>'
        '</div>',
        unsafe_allow_html=True,
    )
    with st.container(key="new_chat_action"):
        st.button(
            "New chat",
            icon=":material/add:",
            use_container_width=True,
            on_click=new_chat,
            disabled=st.session_state.request_in_progress,
        )

    st.markdown('<div class="conversation-heading">Conversations</div>', unsafe_allow_html=True)
    with st.container(key="conversation_list"):
        if not st.session_state.conversations:
            st.markdown('<div class="conversation-empty">No conversations yet</div>', unsafe_allow_html=True)
        for conversation in st.session_state.conversations:
            active = conversation.id == st.session_state.active_conversation_id
            title = conversation.title.strip() or "Untitled conversation"
            row_key = "active_conversation_row" if active else f"conversation_{conversation.id}"
            with st.container(key=row_key):
                row = st.columns([6, 1], gap="small", vertical_alignment="center")
                if row[0].button(
                    title,
                    key=f"open-{conversation.id}",
                    type="tertiary",
                    use_container_width=True,
                    disabled=st.session_state.request_in_progress,
                    wrap=True,
                ):
                    load_conversation(conversation.id)
                    st.rerun()
                if row[1].button(
                    "Delete",
                    icon=":material/delete_outline:",
                    key=f"delete-{conversation.id}",
                    help=f"Delete {title}",
                    type="tertiary",
                    disabled=st.session_state.request_in_progress,
                ):
                    st.session_state.pending_delete_id = conversation.id
                    st.rerun()

    pending_delete = st.session_state.pending_delete_id
    if pending_delete:
        st.warning("Delete this conversation?")
        confirm, cancel = st.columns(2)
        if confirm.button("Delete", type="primary", use_container_width=True):
            try:
                client.delete_conversation(pending_delete)
                if pending_delete == st.session_state.active_conversation_id:
                    new_chat()
                st.session_state.pending_delete_id = None
                refresh_conversations()
            except ConversationNotFoundError:
                if pending_delete == st.session_state.active_conversation_id:
                    reset_for_missing_conversation()
                st.session_state.pending_delete_id = None
                refresh_conversations()
            except (BackendUnavailableError, BackendTimeoutError, BackendValidationError, BackendRequestError):
                st.session_state.last_error = "The request failed. Check the backend terminal for details."
            st.rerun()
        if cancel.button("Cancel", use_container_width=True):
            st.session_state.pending_delete_id = None
            st.rerun()

    health = st.session_state.get("health")
    with st.container(key="sidebar_footer"):
        st.radio("Appearance", ("Light", "Dark"), key="appearance", horizontal=True)
        if not st.session_state.backend_available:
            health_markup = '<span class="health-dot offline">●</span>Backend offline'
        elif health and health.status == "healthy":
            health_markup = '<span class="health-dot">●</span>Backend online'
        else:
            health_markup = '<span class="health-dot degraded">●</span>Backend degraded'
        st.markdown(f'<div class="health-line">{health_markup}</div>', unsafe_allow_html=True)
        st.markdown(
            '<div class="memory-note">Chats are stored in backend memory</div>',
            unsafe_allow_html=True,
        )

st.markdown(theme_css(st.session_state.appearance), unsafe_allow_html=True)

with st.container(key="app_header"):
    st.markdown(
        '<header class="app-header">'
        '<span class="shield-mark" aria-hidden="true"></span>'
        '<div><div class="app-title-row">'
        '<span class="app-title">NIST AI Risk Assistant</span>'
        '<span class="local-badge">Local model</span>'
        '</div><div class="app-subtitle">Grounded answers from three NIST AI risk-management publications</div>'
        '</div></header>',
        unsafe_allow_html=True,
    )

if st.session_state.last_error:
    if "memory was reset" in st.session_state.last_error:
        st.warning(st.session_state.last_error)
    else:
        st.error(st.session_state.last_error)

if not st.session_state.messages:
    with st.container(key="empty_state"):
        st.markdown(
            '<div class="empty-copy">'
            '<div class="eyebrow">YOUR LOCAL RESEARCH COMPANION</div>'
            '<div class="empty-title">Ask the NIST AI Risk corpus</div>'
            '<div class="empty-description">Explore the AI Risk Management Framework, the '
            'Generative AI Profile, and practical Playbook guidance.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        with st.container(key="suggestion_grid"):
            for pair_start in range(0, len(EXAMPLE_QUESTIONS), 2):
                example_columns = st.columns(2)
                for column, (category, example) in zip(
                    example_columns, EXAMPLE_QUESTIONS[pair_start : pair_start + 2]
                ):
                    column.button(
                        f"{category}\n{example}",
                        key=f"example-{category}",
                        on_click=choose_example,
                        args=(example,),
                        use_container_width=True,
                        disabled=st.session_state.request_in_progress,
                        wrap=True,
                    )
        st.markdown(
            '<div class="empty-disclaimer">Summarizes NIST guidance. Not legal advice.</div>',
            unsafe_allow_html=True,
        )
else:
    with st.container(key="conversation_messages"):
        for chat_message in st.session_state.messages:
            render_message(chat_message)


pending_status = None
pending_thinking_preview = None
pending_thinking_full = None
pending_answer = None
pending_sources = None
pending_timing = None
if st.session_state.request_in_progress and st.session_state.pending_question:
    with st.container(key="pending_turn"):
        with st.chat_message("user"):
            st.markdown(st.session_state.pending_question)
        with st.chat_message("assistant"):
            st.markdown(
                '<div class="assistant-label"><span aria-hidden="true">◆</span> Assistant</div>',
                unsafe_allow_html=True,
            )
            with st.container(key="working_state"):
                pending_status = st.empty()
            if st.session_state.pending_thinking:
                pending_thinking_preview = st.empty()
                with st.expander("View full thinking", expanded=False):
                    pending_thinking_full = st.empty()
            pending_answer = st.empty()
            pending_sources = st.empty()
            pending_timing = st.empty()


with st.container(key="composer_shell"):
    composer_input, composer_toggle = st.columns([8, 1.6], vertical_alignment="center")
    with composer_input:
        submitted_question = st.chat_input(
            "Ask about NIST AI risk guidance…",
            key="question_draft",
            max_chars=2000,
            disabled=st.session_state.request_in_progress,
        )
    with composer_toggle:
        st.toggle(
            "Think",
            key="thinking_enabled",
            help="Thinking mode may improve complex answers but takes longer on the local model.",
            disabled=st.session_state.request_in_progress,
        )
    st.markdown('<div class="composer-note">Enter to send · Answers use the local document index</div>', unsafe_allow_html=True)


queued_question = st.session_state.queued_question
if queued_question:
    st.session_state.queued_question = None
question_to_submit = queued_question or submitted_question

if question_to_submit and not st.session_state.request_in_progress:
    clean_question = str(question_to_submit).strip()
    if not clean_question:
        st.session_state.last_error = "Enter a question before sending."
        st.rerun()
    st.session_state.request_in_progress = True
    st.session_state.last_error = None
    st.session_state.pending_question = clean_question
    st.session_state.pending_thinking = st.session_state.thinking_enabled
    st.rerun()

if st.session_state.request_in_progress and st.session_state.pending_question:
    clean_question = st.session_state.pending_question
    requested_thinking = st.session_state.pending_thinking
    active_conversation_id = st.session_state.active_conversation_id
    try:
        assert pending_status is not None and pending_answer is not None
        assert pending_sources is not None and pending_timing is not None
        stream_state = {
            "status": "Working locally...",
            "thinking": "",
            "answer": "",
            "completed": None,
            "last_render": 0.0,
            "elapsed": 0,
        }

        def render_status(elapsed: WaitingStatus) -> None:
            stream_state["elapsed"] = elapsed.elapsed_seconds
            pending_status.markdown(
                working_markup(
                    WaitingStatus(str(stream_state["status"]), int(stream_state["elapsed"]))
                ),
                unsafe_allow_html=True,
            )

        def render_deltas(*, force: bool = False) -> None:
            now = monotonic()
            if not force and now - float(stream_state["last_render"]) < 0.08:
                return
            thinking_text = str(stream_state["thinking"])
            answer_text = str(stream_state["answer"])
            if pending_thinking_preview is not None and pending_thinking_full is not None and thinking_text:
                first_paragraph = thinking_text.split("\n\n", 1)[0].strip()
                preview = first_paragraph[:320] + ("…" if len(first_paragraph) > 320 else "")
                pending_thinking_preview.markdown(
                    '<div class="thinking-preview">'
                    '<div class="thinking-label"><span aria-hidden="true">▸</span> Thinking</div>'
                    f'<div class="thinking-copy">{html.escape(preview)}</div></div>',
                    unsafe_allow_html=True,
                )
                pending_thinking_full.markdown(thinking_text)
            if answer_text:
                pending_answer.markdown(answer_text)
            stream_state["last_render"] = now

        def handle_event(event: StreamEvent) -> None:
            if isinstance(event, StatusEvent):
                stream_state["status"] = event.message
                render_status(
                    WaitingStatus(event.message, int(stream_state["elapsed"]))
                )
            elif isinstance(event, ThinkingDeltaEvent):
                stream_state["thinking"] = str(stream_state["thinking"]) + event.delta
                render_deltas()
            elif isinstance(event, AnswerDeltaEvent):
                stream_state["answer"] = str(stream_state["answer"]) + event.delta
                render_deltas()
            elif isinstance(event, SourcesEvent):
                with pending_sources.container():
                    render_sources(event.sources)
            elif isinstance(event, CompletedEvent):
                stream_state["completed"] = event
                stream_state["thinking"] = str(stream_state["thinking"]).strip()
                stream_state["answer"] = str(stream_state["answer"]).strip()
                render_deltas(force=True)
                pending_timing.caption(
                    f"Retrieved in {event.retrieval_seconds:.2f}s · "
                    f"Generated in {event.generation_seconds:.2f}s"
                )

        pump_stream(
            lambda: client.query_stream(
                clean_question,
                active_conversation_id,
                requested_thinking,
            ),
            handle_event,
            render_status,
        )
        completed = stream_state["completed"]
        if completed is None:
            raise BackendValidationError("backend stream ended before completion")
        assert isinstance(completed, CompletedEvent)

        st.session_state.active_conversation_id = completed.conversation_id
        conversation = client.get_conversation(completed.conversation_id)
        refreshed_messages = [item.for_display() for item in conversation.messages]
        if refreshed_messages and refreshed_messages[-1].role == "assistant":
            assistant = refreshed_messages[-1]
            refreshed_messages[-1] = assistant.model_copy(
                update={
                    "retrieval_seconds": completed.retrieval_seconds,
                    "generation_seconds": completed.generation_seconds,
                    "thinking_requested": requested_thinking,
                }
            )
        st.session_state.messages = refreshed_messages
        refresh_conversations()
        st.session_state.clear_question_input = True
    except (
        BackendUnavailableError,
        BackendTimeoutError,
        ConversationNotFoundError,
        BackendGenerationError,
        BackendValidationError,
        BackendRequestError,
    ) as error:
        st.session_state.last_error = friendly_query_error(error)
        st.session_state.restore_question_input = clean_question
    finally:
        st.session_state.request_in_progress = False
        st.session_state.pending_question = None
        st.session_state.pending_thinking = False
    st.rerun()
