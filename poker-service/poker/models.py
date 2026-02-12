from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.validators import MinValueValidator
from django.contrib.auth.hashers import make_password, check_password
import uuid
import random
import string
import statistics
from .constants import PokerConstant
from .services import RoomService

def generate_room_code():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def generate_auth_key():
    return str(uuid.uuid4())


class Room(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(
        max_length=255,
        verbose_name=_("model_room_name_verbose"),
        help_text=_("model_room_name_help_text"),
    )
    room_code = models.CharField(
        max_length=6,
        unique=True,
        default=generate_room_code,
        verbose_name=_("model_room_room_code_verbose"),
        help_text=_("model_room_room_code_help_text"),
    )
    room_password = models.CharField(
        max_length=255,
        verbose_name=_("model_room_room_password_verbose"),
        help_text=_("model_room_room_password_help_text"),
    )
    revealed = models.BooleanField(
        default=False,
        verbose_name=_("model_room_revealed_verbose"),
        help_text=_("model_room_revealed_help_text"),
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("model_room_created_at_verbose"),
        help_text=_("model_room_created_at_help_text"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("model_room_is_active_verbose"),
        help_text=_("model_room_is_active_help_text"),
    )
    
    class Meta:
        verbose_name = _("model_room_verbose")
        verbose_name_plural = _("model_room_verbose_plural")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room_code']),
            models.Index(fields=['is_active', '-created_at']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.room_code})"
    
    def save(self, *args, **kwargs):
        if not self.pk:
            self.room_code = generate_room_code()

            while Room.objects.filter(room_code=self.room_code).exists():
                self.room_code = generate_room_code()

            self.sync_create_to_firebase(self.room_password)
            self.room_password = self.hash_password(self.room_password)

        super().save(*args, **kwargs)
    
    def reset_votes(self):
        active_tasks = self.tasks.filter(is_active=True)

        TaskVote.objects.filter(task__in=active_tasks).delete()

        active_tasks.update(sp=None, metrics={})

        self.revealed = False

        self.save(update_fields=["revealed"])
    
    def reveal_votes(self):
        self.revealed = True

        self.save(update_fields=["revealed"])
    
    def get_active_participants(self):
        return self.participants.filter(is_active=True)
    
    def get_participant_count(self):
        return self.get_active_participants().count()
    
    def hash_password(self, raw_password: str) -> str:
        return make_password(raw_password)

    def set_password(self, raw_password: str):
        self.room_password = self.hash_password(raw_password)
    
        self.save(update_fields=["room_password"])

    def check_password(self, raw_password: str) -> bool:
        return check_password(raw_password, self.room_password)

    def sync_create_to_firebase(self, raw_password: str):
        room_service = RoomService()
        room_code = self.room_code
        
        room_service.create_room(room_code=room_code, password=raw_password)

class Participant(models.Model):
    id = models.AutoField(primary_key=True)
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='participants',
        verbose_name=_("model_participant_room_verbose"),
        help_text=_("model_participant_room_help_text"),
    )
    name = models.CharField(
        max_length=255,
        verbose_name=_("model_participant_name_verbose"),
        help_text=_("model_participant_name_help_text"),
    )
    authentication_key = models.CharField(
        max_length=255,
        default=generate_auth_key,
        verbose_name=_("model_participant_authentication_key_verbose"),
        help_text=_("model_participant_authentication_key_help_text"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("model_participant_is_active_verbose"),
        help_text=_("model_participant_is_active_help_text"),
    )

    class Meta:
        verbose_name = _("model_participant_verbose")
        verbose_name_plural = _("model_participant_verbose_plural")
        unique_together = [
            ['room', 'name'],
            ['room', 'authentication_key'],
        ]
        indexes = [
            models.Index(fields=['authentication_key']),
            models.Index(fields=['room', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.room.room_code}"
    
    def save(self, *args, **kwargs):
        if not self.pk and not self.authentication_key:
            self.authentication_key = generate_auth_key()

        super().save(*args, **kwargs)
    
    def has_voted_for_task(self, task):
        return self.votes.filter(task=task).exists()
    
    def get_vote_for_task(self, task):
        try:
            return self.votes.get(task=task)
        except TaskVote.DoesNotExist:
            return None


class Task(models.Model):
    STATUS_CHOICES = [
        ('pending', _('model_task_status_pending')),
        ('voting', _('model_task_status_voting')),
        ('estimated', _('model_task_status_estimated')),
        ('completed', _('model_task_status_completed')),
    ]

    id = models.AutoField(primary_key=True)
    room = models.ForeignKey(
        Room,
        on_delete=models.CASCADE,
        related_name='tasks',
        verbose_name=_("model_task_room_verbose"),
        help_text=_("model_task_room_help_text"),
    )
    title = models.CharField(
        max_length=500,
        verbose_name=_("model_task_title_verbose"),
        help_text=_("model_task_title_help_text"),
    )
    description = models.TextField(
        verbose_name=_("model_task_description_verbose"),
        help_text=_("model_task_description_help_text"),
        blank=True,
        null=True
    )
    sp = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("model_task_sp_verbose"),
        help_text=_("model_task_sp_help_text"),
        validators=[MinValueValidator(0)]
    )
    metrics = models.JSONField(
        default=dict,
        blank=True,
        verbose_name=_("model_task_metrics_verbose"),
        help_text=_("model_task_metrics_help_text"),
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name=_("model_task_status_verbose"),
        help_text=_("model_task_status_help_text"),
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name=_("model_task_is_active_verbose"),
        help_text=_("model_task_is_active_help_text"),
    )
    created_at = models.DateTimeField(
        default=timezone.now,
        verbose_name=_("model_task_created_at_verbose"),
        help_text=_("model_task_created_at_help_text"),
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("model_task_updated_at_verbose"),
        help_text=_("model_task_updated_at_help_text"),
    )
    
    class Meta:
        verbose_name = _("model_task_verbose")
        verbose_name_plural = _("model_task_verbose_plural")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['room', 'is_active']),
            models.Index(fields=['room', 'status']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.room.room_code}"
    
    def save(self, *args, **kwargs):
        update_fields = kwargs.get('update_fields')

        self.calculate_metrics()

        if update_fields is not None:
            update_fields = set(update_fields)
            update_fields.add('metrics')
            kwargs['update_fields'] = update_fields

        super().save(*args, **kwargs)

    def calculate_metrics(self):
        if not self.pk:
            return

        votes = self.votes.select_related('participant')
        
        if not votes.exists():
            self.metrics = {}

            return
        
        numeric_votes = []
        vote_distribution = {}
        
        for vote in votes:
            vote_value = vote.vote
            
            # Vote distribution
            if vote_value in vote_distribution:
                vote_distribution[vote_value] += 1
            else:
                vote_distribution[vote_value] = 1
            
            try:
                numeric_value = float(vote_value)
                numeric_votes.append(numeric_value)
            except (ValueError, TypeError):
                continue
        
        metrics = {
            'total_votes': votes.count(),
            'distribution': vote_distribution,
        }
        
        if numeric_votes:
            metrics['average'] = round(statistics.mean(numeric_votes), 2)
            metrics['median'] = statistics.median(numeric_votes)
            metrics['min'] = min(numeric_votes)
            metrics['max'] = max(numeric_votes)
            
            # Standard deviation (at least 2 values ​​required)
            if len(numeric_votes) >= 2:
                metrics['std_dev'] = round(statistics.stdev(numeric_votes), 2)
            else:
                metrics['std_dev'] = 0
            
            # Mod
            try:
                metrics['mode'] = statistics.mode(numeric_votes)
            except statistics.StatisticsError:
                from collections import Counter
                counter = Counter(numeric_votes)
                max_count = max(counter.values())
                modes = [k for k, v in counter.items() if v == max_count]
                metrics['modes'] = modes
            
            # Compromise score (according to std_dev)
            if metrics['std_dev'] == 0:
                metrics['consensus_score'] = 100
            else:
                # If the standard deviation is low, the consensus is high.
                consensus = max(0, 100 - (metrics['std_dev'] * 10))
                metrics['consensus_score'] = round(consensus, 2)
        
        self.metrics = metrics
    
    def reset_votes(self):
        self.votes.all().delete()
        self.metrics = {}
        self.sp = None
        self.status = 'pending'
        self.save()
    
    def get_vote_count(self):
        return self.votes.count()
    
    def get_participant_vote(self, participant):
        try:
            return self.votes.get(participant=participant)
        except TaskVote.DoesNotExist:
            return None
    
    def has_all_votes(self):
        active_participants = self.room.get_active_participants().count()
        vote_count = self.get_vote_count()

        return active_participants > 0 and vote_count >= active_participants


class TaskVote(models.Model):
    id = models.AutoField(primary_key=True)
    task = models.ForeignKey(
        Task,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name=_("model_task_vote_task_verbose"),
        help_text=_("model_task_vote_task_help_text"),
    )
    participant = models.ForeignKey(
        Participant,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name=_("model_task_vote_participant_verbose"),
        help_text=_("model_task_vote_participant_help_text"),
    )
    vote = models.CharField(
        max_length=10,
        verbose_name=_("model_task_vote_vote_verbose"),
        help_text=_("model_task_vote_vote_help_text"),
    )
    voted_at = models.DateTimeField(
        auto_now=True,
        verbose_name=_("model_task_vote_voted_at_verbose"),
        help_text=_("model_task_vote_voted_at_help_text"),
    )
    
    class Meta:
        verbose_name = _("model_task_vote_verbose")
        verbose_name_plural = _("model_task_vote_verbose_plural")
        unique_together = [['task', 'participant']]
        ordering = ['voted_at']
        indexes = [
            models.Index(fields=['task', 'participant']),
            models.Index(fields=['task', 'voted_at']),
        ]
    
    def __str__(self):
        return f"{self.participant.name} - {self.task.title}: {self.vote}"
    
    @classmethod
    def get_valid_votes(cls):
        return PokerConstant.POINTS
    
    def is_numeric(self):
        try:
            float(self.vote)

            return True
        except (ValueError, TypeError):
            return False
