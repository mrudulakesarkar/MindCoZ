import json

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings

from .models import ChatMessage, SensorReading


class ApiTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="student",
            password="test-password",
        )
        self.client.force_login(self.user)

    def test_health(self):
        response = self.client.get("/api/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_chat_persists_user_and_fallback_messages(self):
        response = self.client.post(
            "/api/chat",
            data=json.dumps({"message": "I had a difficult day."}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["llm_enabled"])
        self.assertEqual(ChatMessage.objects.count(), 2)
        self.assertEqual(ChatMessage.objects.first().content, "I had a difficult day.")
        self.assertEqual(ChatMessage.objects.first().user, self.user)

    def test_chat_rejects_empty_and_oversized_messages(self):
        empty_response = self.client.post(
            "/api/chat",
            data=json.dumps({"message": "  "}),
            content_type="application/json",
        )
        oversized_response = self.client.post(
            "/api/chat",
            data=json.dumps({"message": "a" * 2001}),
            content_type="application/json",
        )

        self.assertEqual(empty_response.status_code, 400)
        self.assertEqual(oversized_response.status_code, 400)
        self.assertEqual(ChatMessage.objects.count(), 0)

    def test_history_returns_persisted_messages(self):
        ChatMessage.objects.create(user=self.user, role="user", content="Hello")

        response = self.client.get("/api/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["messages"][0]["content"], "Hello")

    def test_chat_and_history_require_authentication(self):
        self.client.logout()

        history_response = self.client.get("/api/history")
        chat_response = self.client.post(
            "/api/chat",
            data=json.dumps({"message": "Hello"}),
            content_type="application/json",
        )

        self.assertEqual(history_response.status_code, 401)
        self.assertEqual(chat_response.status_code, 401)

    def test_history_only_returns_current_users_messages(self):
        other_user = get_user_model().objects.create_user(
            username="another-student",
            password="test-password",
        )
        ChatMessage.objects.create(user=self.user, role="user", content="My message")
        ChatMessage.objects.create(
            user=other_user, role="user", content="Another message"
        )

        response = self.client.get("/api/history")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [message["content"] for message in response.json()["messages"]],
            ["My message"],
        )

    def test_login_and_logout_manage_session(self):
        self.client.logout()
        login_response = self.client.post(
            "/api/login",
            data=json.dumps(
                {"username": "student", "password": "test-password"}
            ),
            content_type="application/json",
        )
        logout_response = self.client.post("/api/logout")
        history_response = self.client.get("/api/history")

        self.assertEqual(login_response.status_code, 200)
        self.assertEqual(logout_response.status_code, 200)
        self.assertEqual(history_response.status_code, 401)

    def test_login_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        body = json.dumps({"username": "student", "password": "test-password"})

        rejected = client.post(
            "/api/login", data=body, content_type="application/json"
        )
        client.get("/api/csrf")
        csrf_token = client.cookies["csrftoken"].value
        accepted = client.post(
            "/api/login",
            data=body,
            content_type="application/json",
            HTTP_X_CSRFTOKEN=csrf_token,
        )

        self.assertEqual(rejected.status_code, 403)
        self.assertEqual(accepted.status_code, 200)

    def test_sensor_reports_unavailable_without_readings(self):
        response = self.client.get("/api/sensor")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"available": False, "status": "unavailable", "reading": None},
        )

    @override_settings(MINDCOZ_SENSOR_API_TOKEN="test-token")
    def test_sensor_requires_authorization_and_accepts_valid_reading(self):
        unauthorized = self.client.post(
            "/api/sensor",
            data=json.dumps({"heart_rate": 72, "spo2": 98}),
            content_type="application/json",
        )
        accepted = self.client.post(
            "/api/sensor",
            data=json.dumps({"heart_rate": 72, "spo2": 98}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer test-token",
        )

        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(accepted.status_code, 201)
        self.assertEqual(SensorReading.objects.count(), 1)
        self.assertTrue(self.client.get("/api/sensor").json()["available"])

    @override_settings(MINDCOZ_SENSOR_API_TOKEN="test-token")
    def test_sensor_rejects_out_of_range_or_boolean_values(self):
        for reading in (
            {"heart_rate": 0, "spo2": 98},
            {"heart_rate": True, "spo2": 98},
            {"heart_rate": 10**1000, "spo2": 98},
            {"heart_rate": 72, "spo2": 101},
        ):
            response = self.client.post(
                "/api/sensor",
                data=json.dumps(reading),
                content_type="application/json",
                HTTP_AUTHORIZATION="Bearer test-token",
            )
            self.assertEqual(response.status_code, 400)

        self.assertEqual(SensorReading.objects.count(), 0)

    def test_sensor_ingestion_is_unavailable_without_configured_token(self):
        response = self.client.post(
            "/api/sensor",
            data=json.dumps({"heart_rate": 72, "spo2": 98}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 503)
