from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import CustomUser, GameRoom

# Hiển thị CustomUser trong admin
@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser
    list_display = ['username', 'email', 'reward_points', 'is_staff']
    fieldsets = UserAdmin.fieldsets + (
        ('Reward System', {'fields': ('reward_points',)}),
    )

# Hiển thị GameRoom trong admin
@admin.register(GameRoom)
class GameRoomAdmin(admin.ModelAdmin):
    list_display = [
        'room_code', 'host', 'guest', 'difficulty',
        'host_score', 'guest_score', 'winner', 'status', 'created_at'
    ]
    list_filter = ['status', 'difficulty']
    search_fields = ['room_code', 'host__username', 'guest__username']
