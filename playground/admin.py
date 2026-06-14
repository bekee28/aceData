from django.contrib import admin
from .models import CustomUser, Purchase
from django.contrib.auth.admin import UserAdmin


@admin.register(Purchase)
class PurchaseAdmin(admin.ModelAdmin):
    list_display = ('item_name', 'user', 'user_name', 'amount_paid', 'date_of_purchase', 'time_of_purchase')
    list_filter = ('item_name', 'date_of_purchase')
    search_fields = ('user__username', 'user_name', 'item_name')
    raw_id_fields = ('user',)
    ordering = ('-date_of_purchase', '-time_of_purchase')

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active', 'date_joined')  # Customize the fields you want to display
    list_filter = ('is_staff', 'is_active')  # Optional: Add filters for easier navigation
    search_fields = ('username', 'email')  # Optional: Add search functionality
    ordering = ('-date_joined',)  # Optional: Specify default ordering

#admin.site.register(CustomUser, CustomUserAdmin)