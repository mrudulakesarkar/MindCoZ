from django.conf import settings
from django.db import models


class ChatMessage(models.Model):
    ROLE_CHOICES = [
        ("user", "User"),
        ("assistant", "Assistant"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_messages",
    )
    role = models.CharField(max_length=9, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]


class SensorReading(models.Model):
    heart_rate = models.FloatField()
    spo2 = models.FloatField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-id"]
