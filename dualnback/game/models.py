from django.db import models
from django.contrib.auth.models import AbstractUser

# Đây là user mở rộng có thêm reward_points
class CustomUser(AbstractUser):
    reward_points = models.IntegerField(default=0)
    highest_level = models.IntegerField(default=1)
    f1_of_highest_level = models.IntegerField(default=0)
class GameRoom(models.Model):
    sequence = models.JSONField(null=True, blank=True)
    ROOM_STATUS_CHOICES = [
        ('waiting', 'Waiting'),
        ('playing', 'Playing'),
        ('finished', 'Finished'),
    ]
    host_ready = models.BooleanField(default=False)
    guest_ready = models.BooleanField(default=False)
    room_code = models.CharField(max_length=10, unique=True)
    host = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='hosted_rooms')
    guest = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='joined_rooms')
    difficulty = models.IntegerField(default=2)
    status = models.CharField(max_length=10, choices=ROOM_STATUS_CHOICES, default='waiting')
    created_at = models.DateTimeField(auto_now_add=True)
    host_total_answered = models.IntegerField(default=0)
    guest_total_answered = models.IntegerField(default=0)
    length = models.IntegerField(default=20)
    n_back = models.IntegerField(default=2)
    delay = models.IntegerField(default=3)
     # Các trường điểm
    host_score = models.IntegerField(default=0)
    guest_score = models.IntegerField(default=0)

    # Người thắng (hoặc null nếu hòa)
    winner = models.ForeignKey('CustomUser', on_delete=models.SET_NULL, null=True, blank=True, related_name='won_games')
    def both_ready(self):
        return self.host_ready and self.guest_ready
    def __str__(self):
        return f"Room {self.room_code} ({self.status})"

    def set_winner(self):
        if self.host_score > self.guest_score:
            self.winner = self.host
        elif self.guest_score > self.host_score:
            self.winner = self.guest
        else:
            self.winner = None  # Hòa
        self.save()
class SingleGameRoom(models.Model):
    sequence = models.JSONField(null=True, blank=True)
    host_ready = models.BooleanField(default=False)
    host = models.ForeignKey(
    'CustomUser',
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name='single_game_rooms'
)
    difficulty = models.IntegerField(default=2)
    created_at = models.DateTimeField(auto_now_add=True)
    host_total_answered = models.IntegerField(default=0)
    level = models.IntegerField(default=0)
     # Các trường điểm
    host_score = models.IntegerField(default=0)

