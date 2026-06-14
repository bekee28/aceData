# Import the required Django modules
from django.conf import settings
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib import admin
#from django.utils import timezone

class CustomUser(AbstractUser):
    primary_key = models.AutoField(primary_key=True)


class Purchase(models.Model):
    # Stripe event id that produced this row. Unique so a webhook retry of the
    # same `checkout.session.completed` event can't create a duplicate purchase.
    # Nullable for manually created/legacy rows that have no originating event.
    event_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    # Linked account (nullable: kept for guest purchases and legacy rows).
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='purchases',
    )
    # Denormalized username/label, retained as a fallback when `user` is unset.
    user_name = models.CharField(max_length=100, default='-')
    item_name = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_of_purchase = models.DateField(null=True)
    time_of_purchase = models.TimeField(null=True)

    def __str__(self):
        return f"{self.user_name} - {self.item_name} - ${self.amount_paid} - {self.date_of_purchase} - {self.time_of_purchase}"

