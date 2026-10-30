from django.conf import settings
from django.db import models


class Notification(models.Model):
    class Type(models.TextChoices):
        DUE_SOON = 'due_soon', "To'lov muddati yaqinlashdi"
        OVERDUE = 'overdue', "To'lov muddati o'tdi"
        DELETE_REQUEST = 'delete_request', "O'chirish so'rovi"
        DELETE_DECIDED = 'delete_decided', "So'rov natijasi"
        CASH_CLOSING = 'cash_closing', 'Kassa yopishga yuborildi'
        CASH_MISMATCH = 'cash_mismatch', 'Kassada farq aniqlandi'
        INSTRUCTOR_ASSIGNED = 'instructor_assigned', 'Instruktorga biriktirildi'

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=30, choices=Type.choices)
    title = models.CharField(max_length=255)
    body = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    link = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['user', 'is_read'])]

    def __str__(self):
        return self.title
