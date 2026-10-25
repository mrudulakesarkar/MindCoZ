# MindCoZ Backend API Contract

All endpoints use JSON. The routes do not include a trailing slash.

## Session authentication and CSRF

Chat and history require an authenticated Django session. User accounts must
currently be provisioned by an administrator; there is no public registration
endpoint. `POST /api/login` accepts `{"username": "...", "password": "..."}`;
`POST /api/logout` ends the current session. Invalid credentials return `401`.

Before login or another state-changing request, call `GET /api/csrf` and retain
the `csrftoken` cookie. Send its value in the `X-CSRFToken` header on
`POST /api/login`, `/api/logout`, and `/api/chat`, and include the session and
CSRF cookies in browser requests. The API currently assumes same-origin
frontend requests; cross-origin deployment has not been configured.

```json
{"status": "ok"}
```

## `GET /api/health`

Returns `200` when the Django application is responding:

```json
{"status": "ok"}
```

This is an application availability check, not a hardware connectivity check.

## `POST /api/chat`

Submit a message as `{"message": "..."}`. Messages must be non-empty strings of
at most 2,000 characters. Both the submitted message and the fixed fallback
response are persisted in SQLite.

```json
{"response": "Thanks for sharing. I can listen, but this is a basic fallback response, not an AI-generated answer.", "llm_enabled": false}
```

Invalid JSON, a missing/invalid message, or an oversized message returns `400`.
The endpoint currently does not call an LLM.

Chat submission and history retrieval require authentication, and messages
are isolated to the authenticated user.

## `GET /api/history`

Returns the authenticated user's most recent 100 persisted chat messages in
chronological order:

```json
{
  "messages": [
    {"id": 1, "role": "user", "content": "Hello", "created_at": "2026-10-25T11:54:42Z"}
  ]
}
```

## `GET /api/sensor`

Returns the latest valid reading received by the backend. With no stored
reading:

```json
{"available": false, "status": "unavailable", "reading": null}
```

With a reading, `available` and `status` indicate that a valid reading has
previously been accepted; they do not assert that the device is currently
connected or the reading is fresh.

## `POST /api/sensor`

Requires `Authorization: Bearer <token>`, where the backend token is supplied
through the `MINDCOZ_SENSOR_API_TOKEN` environment variable. If no token is
configured, ingestion returns `503`; an invalid or missing token returns
`401`.

The JSON body is:

```json
{"heart_rate": 72, "spo2": 98}
```

`heart_rate` must be a finite number from 30 through 240 bpm, and `spo2` must
be a finite number from 70 through 100 percent. Accepted readings return `201`.
These values are backend validation limits, not a claim that physical hardware
has been connected or verified.
