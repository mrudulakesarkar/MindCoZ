import hmac
import json
import math
from functools import wraps

from django.conf import settings
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import (
    require_GET,
    require_http_methods,
    require_POST,
)

from .models import ChatMessage, SensorReading


MAX_MESSAGE_LENGTH = 2000
FALLBACK_RESPONSE = (
    "Thanks for sharing. I can listen, but this is a basic fallback response, "
    "not an AI-generated answer."
)


def authenticated_api(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Authentication required"}, status=401)
        return view(request, *args, **kwargs)

    return wrapped


def _json_object(request):
    if request.content_type != "application/json":
        return None, JsonResponse(
            {"error": "Content-Type must be application/json"}, status=415
        )
    try:
        data = json.loads(request.body)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None, JsonResponse({"error": "Invalid JSON body"}, status=400)
    if not isinstance(data, dict):
        return None, JsonResponse({"error": "JSON body must be an object"}, status=400)
    return data, None


@require_GET
@ensure_csrf_cookie
def csrf_token(request):
    return JsonResponse({"status": "ok"})


@require_POST
def login(request):
    data, error = _json_object(request)
    if error:
        return error
    username = data.get("username")
    password = data.get("password")
    if (
        not isinstance(username, str)
        or not username
        or len(username) > 150
        or not isinstance(password, str)
        or not password
        or len(password) > 1024
    ):
        return JsonResponse(
            {"error": "username and password must be non-empty strings"},
            status=400,
        )

    user = authenticate(request, username=username, password=password)
    if user is None:
        return JsonResponse({"error": "Invalid username or password"}, status=401)
    auth_login(request, user)
    return JsonResponse({"status": "authenticated"})


@require_POST
@authenticated_api
def logout(request):
    auth_logout(request)
    return JsonResponse({"status": "logged_out"})


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})


@require_POST
@authenticated_api
def chat(request):
    data, error = _json_object(request)
    if error:
        return error

    message = data.get("message")
    if not isinstance(message, str) or not message.strip():
        return JsonResponse({"error": "message must be a non-empty string"}, status=400)
    message = message.strip()
    if len(message) > MAX_MESSAGE_LENGTH:
        return JsonResponse(
            {"error": f"message must be at most {MAX_MESSAGE_LENGTH} characters"},
            status=400,
        )

    with transaction.atomic():
        ChatMessage.objects.create(user=request.user, role="user", content=message)
        ChatMessage.objects.create(
            user=request.user, role="assistant", content=FALLBACK_RESPONSE
        )

    return JsonResponse(
        {"response": FALLBACK_RESPONSE, "llm_enabled": False},
        status=200,
    )


@require_GET
@authenticated_api
def history(request):
    messages = list(
        ChatMessage.objects.filter(user=request.user).order_by("-id")[:100]
    )
    messages.reverse()
    return JsonResponse(
        {
            "messages": [
                {
                    "id": message.id,
                    "role": message.role,
                    "content": message.content,
                    "created_at": message.created_at,
                }
                for message in messages
            ]
        }
    )


def _sensor_reading_data(reading):
    return {
        "heart_rate": reading.heart_rate,
        "spo2": reading.spo2,
        "received_at": reading.received_at,
    }


def _valid_measurement(value, minimum, maximum):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        numeric_value = float(value)
    except OverflowError:
        return False
    return math.isfinite(numeric_value) and minimum <= numeric_value <= maximum


@csrf_exempt
@require_http_methods(["GET", "POST"])
def sensor(request):
    if request.method == "GET":
        reading = SensorReading.objects.first()
        if reading is None:
            return JsonResponse(
                {"available": False, "status": "unavailable", "reading": None}
            )
        return JsonResponse(
            {
                "available": True,
                "status": "available",
                "reading": _sensor_reading_data(reading),
            }
        )

    configured_token = getattr(settings, "MINDCOZ_SENSOR_API_TOKEN", "")
    if not configured_token:
        return JsonResponse(
            {"error": "Sensor ingestion is not configured"}, status=503
        )
    authorization = request.headers.get("Authorization", "")
    if not hmac.compare_digest(authorization, f"Bearer {configured_token}"):
        return JsonResponse({"error": "Unauthorized"}, status=401)

    data, error = _json_object(request)
    if error:
        return error
    heart_rate = data.get("heart_rate")
    spo2 = data.get("spo2")
    if not _valid_measurement(heart_rate, 30, 240):
        return JsonResponse(
            {"error": "heart_rate must be a finite number from 30 to 240 bpm"},
            status=400,
        )
    if not _valid_measurement(spo2, 70, 100):
        return JsonResponse(
            {"error": "spo2 must be a finite number from 70 to 100 percent"},
            status=400,
        )

    reading = SensorReading.objects.create(heart_rate=heart_rate, spo2=spo2)
    return JsonResponse(
        {"status": "accepted", "reading": _sensor_reading_data(reading)},
        status=201,
    )
