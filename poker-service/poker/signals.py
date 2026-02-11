from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from .models import Participant, Task, TaskVote, Room

def get_task_status(votes_count: int, total_participants:int) -> str:
    if votes_count == 0:
        status = 'pending'
    elif votes_count < total_participants:
        status = 'voting'
    else:
        status = 'estimated'

    return status

def update_tasks_by_room(room):
    total_participants = room.participants.count()
    tasks = room.tasks.prefetch_related('votes')

    for task in tasks:
        total_votes = len(task.votes.all())
        task.status = get_task_status(total_votes, total_participants)
        task.calculate_metrics()

    Task.objects.bulk_update(tasks, ['status', 'metrics'])

def update_task(task):
    total_votes = task.votes.count()
    total_participants = task.room.participants.count()

    new_status = get_task_status(total_votes, total_participants)

    if task.status != new_status:
        task.status = new_status
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
    
    if instance.revealed:
        instance.tasks.update(status='completed')

        return

    update_tasks_by_room(instance)

@receiver(post_delete, sender=Participant)
def participant_leaving(sender, instance, **kwargs):
    room = instance.room
    
    if room.revealed:
        return

    update_tasks_by_room(room)

@receiver(post_save, sender=Participant)
def participant_join(sender, instance, created, **kwargs):
    if not created:
        return
    
    room = instance.room
    
    if room.revealed:
        return

    update_tasks_by_room(room)
