# Import the required Django modules
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib import admin
import uuid
#from django.utils import timezone

class CustomUser(AbstractUser):
    reset_token = models.UUIDField(default=uuid.uuid4, editable=False)
    primary_key = models.AutoField(primary_key=True)

    
class Purchase(models.Model):
    #user = models.ForeignKey(User, on_delete=models.CASCADE)
    user_name = models.CharField(max_length=100, default='-')
    item_name = models.CharField(max_length=100)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    date_of_purchase = models.DateField(null=True)
    time_of_purchase = models.TimeField(null=True)

    def __str__(self):
        return f"{self.user_name} - {self.item_name} - ${self.amount_paid} - {self.date_of_purchase} - {self.time_of_purchase}"

