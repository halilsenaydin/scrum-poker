from typing import Callable, Optional
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Prefetch, QuerySet
from .models import Participant, Task, TaskVote, Room, Sprint

def get_task_status(votes_count: int, total_participants:int) -> str:
    if votes_count == 0:
        status = 'pending'
    elif votes_count < total_participants:
        status = 'voting'
    else:
        status = 'estimated'

    return status

def update_active_sprint_tasks(
    room: Room,
    on_revealed: Optional[Callable[[QuerySet["Task"]], None]] = None
):
    sprint = room.sprints.filter(is_active=True).prefetch_related(
        Prefetch('tasks', queryset=Task.objects.prefetch_related('votes'))
    ).first()
    
    if not sprint:
        return
    
    tasks = sprint.tasks.all()
    
    if sprint.revealed:
        if on_revealed:
            on_revealed(tasks)

        return
    
    total_participants = room.participants.filter(is_active=True).count()
    updated: list[Task] = []

    for task in sprint.tasks.all():
        total_votes = task.votes.count()
        task.status = get_task_status(total_votes, total_participants)

        task.calculate_metrics()
        updated.append(task)

    Task.objects.bulk_update(updated, ['status', 'metrics'])

def update_task(task):
    total_votes = task.votes.count()
    total_participants = task.room.participants.filter(is_active=True).count()

    task.status = get_task_status(total_votes, total_participants)
    task.save(update_fields=['status'])

@receiver(post_save, sender=TaskVote)
def update_task_status_on_vote_save(sender, instance, created, **kwargs):
    update_task(instance.task)

@receiver(post_delete, sender=TaskVote)
def update_task_status_on_vote_delete(sender, instance, **kwargs):
    update_task(instance.task)

@receiver(post_save, sender=Room)
def room_state_changed(sender, instance, created, **kwargs):
    if created:
        return

    update_active_sprint_tasks(instance)

@receiver(post_save, sender=Sprint)
def sprint_state_changed(sender, instance, created, **kwargs):
    if created:
        return

    update_active_sprint_tasks(instance.room, on_revealed=lambda tasks: tasks.update(status='completed'))

@receiver(post_delete, sender=Participant)
def participant_leaving(sender, instance, **kwargs):
    room = instance.room
    
    update_active_sprint_tasks(room)

@receiver(post_save, sender=Participant)
def participant_join(sender, instance, created, **kwargs):
    if not created:
        return
    
    room = instance.room

    update_active_sprint_tasks(room)
