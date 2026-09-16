"""Streamlit UI for the local NIST AI Risk RAG prototype."""

from __future__ import annotations

import os
from pathlib import Path

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
    from .components import render_message
    from .models import Message
    from .styles import CSS
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
    from components import render_message
    from models import Message
    from styles import CSS


FRONTEND_DIR = Path(__file__).resolve().parent
load_dotenv(FRONTEND_DIR / ".env")

st.set_page_config(
    page_title="NIST AI Risk Assistant",
    page_icon="🛡️",
    layout="wide",
)
st.markdown(CSS, unsafe_allow_html=True)

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
        "pending_delete_id": None,
        "queued_question": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value
    if st.session_state.clear_question_input:
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
    if isinstance(error, BackendGenerationError) and (
        "ollama" in str(error).lower() or "qwen3:4b" in str(error).lower()
    ):
        return "Ollama or qwen3:4b is unavailable. Check the backend health status."
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
    requested_thinking = st.session_state.thinking_enabled
    try:
        with st.container(key="pending_turn"):
            # Keep the submitted turn visible while the atomic backend call runs.
            with st.chat_message("user"):
                st.markdown(clean_question)
            with st.container(key="working_state"):
                st.markdown(
                    '<div class="working-title"><span class="working-dot">●</span>'
                    'Working with the local model</div>'
                    '<div class="working-copy">Retrieving relevant NIST passages and '
                    'generating an answer…</div>',
                    unsafe_allow_html=True,
                )
            response = client.query(
                clean_question,
                st.session_state.active_conversation_id,
                requested_thinking,
            )

        st.session_state.active_conversation_id = response.conversation_id
        conversation = client.get_conversation(response.conversation_id)
        refreshed_messages = [item.for_display() for item in conversation.messages]
        if refreshed_messages and refreshed_messages[-1].role == "assistant":
            assistant = refreshed_messages[-1]
            refreshed_messages[-1] = assistant.model_copy(
                update={
                    "retrieval_seconds": response.retrieval_seconds,
                    "generation_seconds": response.generation_seconds,
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
    finally:
        st.session_state.request_in_progress = False
    st.rerun()
