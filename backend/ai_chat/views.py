from __future__ import annotations

import json
import logging

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from .service import respond
from .ollama_client import OllamaError
from .models import AIChatMessage, AIChatSession


def json_response(
    data: dict,
    status: int = 200,
) -> JsonResponse:
    return JsonResponse(
        data,
        status=status,
        json_dumps_params={
            "ensure_ascii":
                False,
        },
    )


def parse_json(request) -> dict:
    if not request.body:
        return {}

    try:
        payload = json.loads(
            request.body.decode(
                "utf-8"
            )
        )
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise ValueError(
            f"JSON không hợp lệ: {exc}"
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise ValueError(
            "Body JSON phải là object."
        )

    return payload


def ensure_session_key(
    request,
) -> str:
    if not request.session.session_key:
        request.session.create()

    return (
        request.session.session_key
        or ""
    )


def session_queryset(
    request,
):
    if request.user.is_authenticated:
        return AIChatSession.objects.filter(
            user=request.user
        )

    return AIChatSession.objects.filter(
        user__isnull=True,
        session_key=
            ensure_session_key(
                request
            ),
    )


def get_or_create_conversation(
    request,
    *,
    conversation_id=None,
    first_message: str = "",
) -> AIChatSession:
    queryset = session_queryset(
        request
    )

    if conversation_id:
        try:
            return queryset.get(
                id=conversation_id
            )
        except AIChatSession.DoesNotExist:
            pass

    title = (
        first_message[:170].strip()
        if first_message
        else "UniConnect AI Chat"
    )

    return AIChatSession.objects.create(
        user=(
            request.user
            if request.user.is_authenticated
            else None
        ),
        session_key=(
            ""
            if request.user.is_authenticated
            else ensure_session_key(
                request
            )
        ),
        title=title,
        context={},
    )


def message_payload(
    message: AIChatMessage,
) -> dict:
    return {
        "id":
            message.id,
        "role":
            message.role,
        "text":
            message.content,
        "intent":
            message.intent,
        "payload":
            message.payload,
        "created_at":
            message.created_at.isoformat(),
    }


@require_POST
def chat_view(request):
    try:
        payload = parse_json(
            request
        )
    except ValueError as exc:
        return json_response(
            {
                "success": False,
                "error": str(exc),
            },
            status=400,
        )

    message = str(
        payload.get(
            "message",
            "",
        )
    ).strip()

    if not message:
        return json_response(
            {
                "success": False,
                "error":
                    "Tin nhắn không được để trống.",
            },
            status=400,
        )

    if len(message) > 2000:
        return json_response(
            {
                "success": False,
                "error":
                    "Tin nhắn tối đa 2000 ký tự.",
            },
            status=400,
        )

    ui_context = payload.get(
        "ui_context",
        {},
    )

    if not isinstance(
        ui_context,
        dict,
    ):
        ui_context = {}

    conversation_id = payload.get(
        "conversation_id"
    )

    conversation = get_or_create_conversation(
        request,
        conversation_id=
            conversation_id,
        first_message=
            message,
    )

    previous_context = (
        conversation.context
        if isinstance(
            conversation.context,
            dict,
        )
        else {}
    )

    try:
        assistant = respond(
            message=message,
            previous_context=
                previous_context,
            ui_context=
                ui_context,
            history=list(reversed(list(
                conversation.messages.order_by('-id').values('role', 'content')[:6]
            ))),
        )
    except OllamaError as exc:
        return json_response(
            {'success': False, 'error': str(exc)}, status=exc.status,
        )
    except Exception as exc:
        logging.getLogger(__name__).exception('AI lookup failed')
        return json_response(
            {
                "success": False,
                "error":
                    "Chưa thể xử lý tư vấn lúc này. Vui lòng thử lại sau.",
            },
            status=500,
        )

    with transaction.atomic():
        AIChatMessage.objects.create(
            conversation=
                conversation,
            role=
                AIChatMessage.ROLE_USER,
            content=
                message,
            intent=
                "user",
            payload={
                "ui_context":
                    ui_context,
            },
        )

        assistant_message = (
            AIChatMessage.objects.create(
                conversation=
                    conversation,
                role=
                    AIChatMessage.ROLE_ASSISTANT,
                content=
                    str(
                        assistant.get(
                            "text",
                            "",
                        )
                    ),
                intent=
                    str(
                        assistant.get(
                            "intent",
                            "",
                        )
                    ),
                payload={
                    "cards":
                        assistant.get(
                            "cards",
                            [],
                        ),
                    "suggestions":
                        assistant.get(
                            "suggestions",
                            [],
                        ),
                    "diagnostics":
                        assistant.get(
                            "diagnostics",
                            {},
                        ),
                },
            )
        )

        conversation.context = (
            assistant.get(
                "context",
                previous_context,
            )
        )

        if (
            not conversation.title
            or conversation.title
            == "UniConnect AI Chat"
        ):
            conversation.title = (
                message[:170]
            )

        conversation.save(
            update_fields=[
                "context",
                "title",
                "updated_at",
            ]
        )

    return json_response(
        {
            "success": True,
            "conversation_id":
                conversation.id,
            "reply": {
                "id":
                    assistant_message.id,
                "role":
                    "assistant",
                "text":
                    assistant_message.content,
                "intent":
                    assistant_message.intent,
                "cards":
                    assistant_message.payload.get(
                        "cards",
                        [],
                    ),
                "suggestions":
                    assistant_message.payload.get(
                        "suggestions",
                        [],
                    ),
                "diagnostics":
                    assistant_message.payload.get(
                        "diagnostics",
                        {},
                    ),
            },
            "context":
                conversation.context,
        }
    )


@require_GET
def chat_history_view(request):
    raw_id = request.GET.get(
        "conversation_id"
    )

    queryset = session_queryset(
        request
    )

    conversation = None

    if raw_id:
        try:
            conversation = queryset.get(
                id=int(
                    raw_id
                )
            )
        except (
            ValueError,
            AIChatSession.DoesNotExist,
        ):
            conversation = None

    if conversation is None:
        conversation = queryset.first()

    if conversation is None:
        return json_response(
            {
                "success": True,
                "conversation_id":
                    None,
                "messages": [],
                "context": {},
            }
        )

    messages = [
        message_payload(
            message
        )
        for message
        in conversation.messages.all()
    ]

    # Flatten structured payload for frontend.
    for item in messages:
        payload = item.pop(
            "payload",
            {}
        )

        if item[
            "role"
        ] == "assistant":
            item[
                "cards"
            ] = payload.get(
                "cards",
                [],
            )
            item[
                "suggestions"
            ] = payload.get(
                "suggestions",
                [],
            )
            item[
                "diagnostics"
            ] = payload.get(
                "diagnostics",
                {},
            )

    return json_response(
        {
            "success": True,
            "conversation_id":
                conversation.id,
            "messages":
                messages,
            "context":
                conversation.context,
        }
    )


@require_POST
def new_chat_view(request):
    conversation = AIChatSession.objects.create(
        user=(
            request.user
            if request.user.is_authenticated
            else None
        ),
        session_key=(
            ""
            if request.user.is_authenticated
            else ensure_session_key(
                request
            )
        ),
        title="UniConnect AI Chat",
        context={},
    )

    return json_response(
        {
            "success": True,
            "conversation_id":
                conversation.id,
            "messages": [],
            "context": {},
        },
        status=201,
    )
