from django.db import models
from .models import SignalEvent


class SignalExecutionLog(models.Model):
    signal = models.OneToOneField(SignalEvent, on_delete=models.CASCADE, related_name='execution')
    executed_at = models.DateTimeField(auto_now_add=True)
    success = models.BooleanField(default=False)
    message = models.TextField(blank=True)

    class Meta:
        indexes = [
            models.Index(fields=['-executed_at']),
        ]

