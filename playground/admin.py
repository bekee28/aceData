from django.contrib import admin
from .models import CustomUser, Purchase
from django.contrib.auth.admin import UserAdmin
#from django.contrib.auth.admin import UserAdmin
#from .models import Purchase

# Register the custom user model with the admin site
#admin.site.register(CustomUser)
admin.site.register(Purchase)

@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    list_display = ('username', 'email', 'is_staff', 'is_active', 'date_joined')  # Customize the fields you want to display
    list_filter = ('is_staff', 'is_active')  # Optional: Add filters for easier navigation
    search_fields = ('username', 'email')  # Optional: Add search functionality
    ordering = ('-date_joined',)  # Optional: Specify default ordering

#admin.site.register(CustomUser, CustomUserAdmin)