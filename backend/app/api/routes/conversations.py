from fastapi import APIRouter, Depends, HTTPException, Response, status

from ..dependencies import get_runtime
from ...schemas.conversation import ConversationResponse, ConversationSummary
from ...services.chat_store import ConversationNotFoundError


router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
def list_conversations(runtime=Depends(get_runtime)) -> list[ConversationSummary]:
    return runtime.store.list()


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(conversation_id: str, runtime=Depends(get_runtime)) -> ConversationResponse:
    try:
        return runtime.store.get(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(conversation_id: str, runtime=Depends(get_runtime)) -> Response:
    try:
        runtime.store.delete(conversation_id)
    except ConversationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Conversation not found") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)
