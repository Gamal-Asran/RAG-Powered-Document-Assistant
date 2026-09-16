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
    "What are the four core functions of the AI RMF?",
    "What risks are associated with generative AI?",
    "How does the Playbook support the GOVERN function?",
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


def choose_example(question: str) -> None:
    st.session_state.question_draft = question


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
    st.title("🛡️ NIST AI Risk")
    health = st.session_state.get("health")
    if not st.session_state.backend_available:
        st.markdown('<span class="health-bad">● Backend offline</span>', unsafe_allow_html=True)
    elif health and health.status == "healthy":
        st.markdown('<span class="health-ok">● Backend healthy</span>', unsafe_allow_html=True)
    else:
        st.markdown('<span class="health-warn">● Backend degraded</span>', unsafe_allow_html=True)

    st.button(
        "＋ New chat",
        use_container_width=True,
        on_click=new_chat,
        disabled=st.session_state.request_in_progress,
    )
    st.caption("Conversations")
    for conversation in st.session_state.conversations:
        row = st.columns([5, 1], gap="small")
        active = conversation.id == st.session_state.active_conversation_id
        title = conversation.title.strip() or "Untitled conversation"
        if len(title) > 42:
            title = title[:39].rstrip() + "…"
        if row[0].button(
            title,
            key=f"open-{conversation.id}",
            type="primary" if active else "secondary",
            use_container_width=True,
            disabled=st.session_state.request_in_progress,
        ):
            load_conversation(conversation.id)
            st.rerun()
        if row[1].button(
            "🗑",
            key=f"delete-{conversation.id}",
            help=f"Delete {title}",
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

    st.divider()
    st.caption("History is stored in memory and disappears when the backend restarts.")


st.title("NIST AI Risk Assistant")
st.markdown(
    '<div class="app-subtitle">Grounded answers from the NIST AI Risk Management Framework, '
    "Generative AI Profile, and AI RMF Playbook.</div>",
    unsafe_allow_html=True,
)

if st.session_state.last_error:
    if "memory was reset" in st.session_state.last_error:
        st.warning(st.session_state.last_error)
    else:
        st.error(st.session_state.last_error)

if not st.session_state.messages:
    st.markdown(
        '<div class="welcome-card">Ask questions about the NIST AI Risk Management Framework, '
        "the Generative AI Profile, and the AI RMF Playbook.</div>",
        unsafe_allow_html=True,
    )
    example_columns = st.columns(3)
    for column, example in zip(example_columns, EXAMPLE_QUESTIONS):
        column.button(
            example,
            key=f"example-{example}",
            on_click=choose_example,
            args=(example,),
            use_container_width=True,
            disabled=st.session_state.request_in_progress,
        )
    st.markdown(
        '<div class="disclaimer">This assistant summarizes NIST guidance and does not provide legal advice.</div>',
        unsafe_allow_html=True,
    )

for chat_message in st.session_state.messages:
    render_message(chat_message)


with st.form("question_form", clear_on_submit=False):
    input_column, think_column, send_column = st.columns([8, 2, 1.35], vertical_alignment="bottom")
    with input_column:
        question = st.text_input(
            "Question",
            key="question_draft",
            max_chars=2000,
            placeholder="Ask a question about NIST AI risk guidance…",
            label_visibility="collapsed",
            disabled=st.session_state.request_in_progress,
        )
    with think_column:
        st.toggle(
            "Think",
            key="thinking_enabled",
            help="Thinking mode may improve complex answers but takes longer on the local model.",
            disabled=st.session_state.request_in_progress,
        )
    with send_column:
        submitted = st.form_submit_button(
            "Send",
            type="primary",
            use_container_width=True,
            disabled=st.session_state.request_in_progress,
        )


if submitted and not st.session_state.request_in_progress:
    clean_question = question.strip()
    if not clean_question:
        st.session_state.last_error = "Enter a question before sending."
        st.rerun()
    st.session_state.request_in_progress = True
    st.session_state.last_error = None
    requested_thinking = st.session_state.thinking_enabled
    try:
        # The script has already rendered stored history for this run, so show the
        # submitted turn immediately while the atomic backend request is pending.
        with st.chat_message("user"):
            st.markdown(clean_question)
        with st.status("Working with the local model…", expanded=True) as status:
            st.write("Retrieving sources and generating a grounded answer…")
            response = client.query(
                clean_question,
                st.session_state.active_conversation_id,
                requested_thinking,
            )
            status.update(label="Answer ready", state="complete", expanded=False)

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
