import json
from django.conf import settings
from django.contrib import messages
from django.db.models import Prefetch
from django.http import HttpResponseRedirect, JsonResponse
from django.forms.models import model_to_dict
from django.shortcuts import render, redirect
from django.utils import translation
from django.utils.decorators import method_decorator
from django.utils.translation import gettext as _
from django.views import View
from django.views.decorators.csrf import csrf_protect
from django.views.generic import TemplateView
from .constants import PokerConstant
from .models import Room, Participant, TaskVote, Task, Sprint
from .services import RoomService, ResultUtil
from .decorators import admin_required, room_not_revealed_required, room_token_required, user_required

class BaseView(View):
    # Page Urls
    HOME_URL = "poker:home"
    ROOM_URL = "poker:room"
    TASK_DETAIL_URL = "poker:task_detail"
    TASKS_URL = "poker:tasks"

    # Cookie Keys
    COOKIE_TOKEN = "token"

    room_service = RoomService()

class BaseTemplateView(TemplateView, BaseView):
    pass

class RoomsHomeView(BaseTemplateView):
    """
    Rooms home view.

    Args:
        TemplateView: Django TemplateView class.

    Returns:
        Renders the home.html template with room join/create functionality.
    """

    template_name = "home.html"
    ACTION_HANDLERS = {
        "join_room": "handle_join_room",
        "create_room": "handle_create_room",
    }

    def post(self, request, *args, **kwargs):
        """
        Post method to handle room join/create actions.

        Args:
            request: Django HTTP request object.
            *args: Additional positional arguments.
            **kwargs: Additional keyword arguments.

        Returns:
            Django HTTP response object.
        """
        for action, handler in self.ACTION_HANDLERS.items():
            if action in request.POST:
                return getattr(self, handler)(request)

        return redirect(self.HOME_URL)

    def handle_join_room(self, request):
        """
        Handle joining a room.

        Args:
            request: Django HTTP request object.

        Returns:
            Django HTTP response object.
        """
        data = request.POST
        room_id = data.get("room_id", "").strip()
        password = data.get("password", "").strip()
        result = self.room_service.join_room(room_id, password)

        if not result.status:
            messages.error(request, result.message)

            return redirect(self.HOME_URL)
        
        response = redirect(self.ROOM_URL, room_id=room_id)
        response.set_cookie(
            self.COOKIE_TOKEN, 
            self.room_service.generate_token(room_id, result.data.get('password')),
            httponly=True,
            samesite="Lax",
            secure=not settings.DEBUG
        )

        return response

    def handle_create_room(self, request):
        """
        Handle creating a new room.

        Args:
            request: Django HTTP request object.

        Returns:
            Django HTTP response object.
        """
        data = request.POST
        password = data.get("new_password", "").strip()
        result = self.room_service.create_room(password)

        if not result.status:
            messages.error(request, result.message)

            return redirect(self.HOME_URL)

        messages.success(request, result.message)

        return redirect(self.ROOM_URL, room_id=result.data["room_code"])

class RoomView(BaseTemplateView):
    template_name = "room.html"

    def dispatch(self, request, *args, **kwargs):
        self.room_id = kwargs.get("room_id")
        self.firebase_room = self.room_service.get_room(self.room_id)
        self.room = Room.objects.filter(room_code=self.room_id).first()
        self.has_room = self.room is not None

        if self.firebase_room is None:
            messages.error(request, _('message_room_not_found'))

            return redirect(self.HOME_URL)

        return super().dispatch(request, *args, **kwargs)
 
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        context.update({
            "room_id": self.room_id,
            "room_name": self.room.name if self.has_room else None,
            "room_": self.firebase_room,
            "has_room": self.has_room,
            "points": PokerConstant.POINTS,
        })

        return context
    
    @room_token_required
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class SprintsView(BaseTemplateView):
    template_name = "sprints.html"

    @user_required
    def dispatch(self, request, *args, **kwargs):
        room_id = kwargs.get("room_id")
        self.room_id = room_id
        self.room = Room.objects.filter(room_code=room_id).first()

        if self.room is None:
            messages.error(request, _('message_room_not_found'))

            return redirect(self.HOME_URL)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sprints = (
            self.room.sprints
            .filter()
        )
        participants = (
            self.room.participants
            .filter(is_active=True)
        )
        user = self.request.user
        is_admin = user.is_superuser

        context.update({
            "is_admin": is_admin,
            "sprints": sprints,
            "room_id": self.room_id,
            "room_name": self.room.name,
            "participants": participants
        })

        return context

    @room_token_required
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

class TaskView(BaseTemplateView):
    template_name = "tasks.html"

    @user_required
    def dispatch(self, request, *args, **kwargs):
        room_id = kwargs.get("room_id")
        sprint_id = kwargs.get("sprint_id")
        self.room_id = room_id
        self.sprint_id = sprint_id
        self.room = Room.objects.filter(room_code=room_id).first()

        if self.room is None:
            messages.error(request, _('message_room_not_found'))

            return redirect(self.HOME_URL)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sprint = Sprint.objects.filter(pk=self.sprint_id).first()
        tasks = []

        if sprint:
            tasks = sprint.tasks.filter(is_active=True)

        participants = (
            self.room.participants
            .filter(is_active=True)
        )
        user = self.request.user
        is_admin = user.is_superuser

        context.update({
            "is_admin": is_admin,
            "tasks": tasks,
            "room_id": self.room_id,
            "room_name": self.room.name,
            "participants": participants,
            "revealed": True if sprint and (is_admin or sprint.revealed) else False
        })

        return context

    @room_token_required
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

@method_decorator(csrf_protect, name="dispatch")
class TaskDetailView(BaseTemplateView):
    template_name = "task_detail.html"
    
    @user_required
    def dispatch(self, request, *args, **kwargs):
        self.room_code=kwargs.get("room_id")
        self.room = Room.objects.filter(
            room_code=self.room_code
        ).first()
        self.sprint_id=kwargs.get("sprint_id")
        self.sprint = Sprint.objects.filter(
            pk=self.sprint_id
        ).first()
        self.task_id=kwargs.get("task_id")

        if not self.room:
            messages.error(request, _("message_room_not_found"))
            return redirect(self.HOME_URL)

        self.task = self.room.tasks.filter(
            id=kwargs.get("task_id"),
            is_active=True
        ).first()

        if not self.task:
            messages.error(request, _("message_task_not_found"))

            return redirect(self.TASKS_URL, room_id=self.room.room_code, sprint_id=self.sprint_id)

        return super().dispatch(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        participants = (
            self.room.participants
            .filter(is_active=True)
            .prefetch_related(
                Prefetch(
                    "votes",
                    queryset=TaskVote.objects.filter(task=self.task),
                    to_attr="task_votes"
                )
            )
        )
        user = self.request.user
        is_admin = user.is_superuser
        revealed = self.sprint.revealed if self.sprint else False
        user_vote = None
        user_vote_obj = self.task.votes.filter(participant__user=user).first()

        if user_vote_obj:
            user_vote = user_vote_obj.vote

        context.update({
            "revealed": revealed,
            "sprint_id": self.sprint_id,
            "room_id": self.room_code,
            "room_name": self.room.name,
            "task_id": self.task_id,
            "points": PokerConstant.POINTS,
            "selected_vote": user_vote,
            "participants": participants,
            "is_admin": is_admin,
            "task": self.task,
            "metrics": self.task.metrics if revealed or is_admin else None,
            "show_vote_display": True
        })

        return context

    @room_not_revealed_required  
    def post(self, request, *args, **kwargs):
        room_id = kwargs["room_id"]
        data = json.loads(request.body)
        vote = data.get("vote")

        try:
            participant = Participant.objects.get(
                user=request.user,
                room__room_code=room_id,
                is_active=True
            )
        except Participant.DoesNotExist:
            result = ResultUtil.error_result(_('message_participant_not_found')).__dict__

            return JsonResponse(result, status=403)
            
        TaskVote.objects.update_or_create(
            task=self.task,
            participant=participant,
            defaults={
                "vote": vote
            }
        )

        result = ResultUtil.success_result(_('message_vote_success'), {
            "vote": vote
        }).__dict__

        return JsonResponse(result)
    
    @admin_required
    def patch(self, request, *args, **kwargs):
        room_id = kwargs["room_id"]
        task_id = kwargs["task_id"]
        data = json.loads(request.body)
        sp = data.get("sp")
        sp = sp if sp and sp != "" else None

        try:
            task = Task.objects.get(id=task_id, room__room_code=room_id)
        except Task.DoesNotExist:
            task = None

        if not task:
            result = ResultUtil.error_result(_('message_task_not_found')).__dict__
            
            return JsonResponse(result, status=404)

        task.sp = sp
        task.save(update_fields=["sp"])

        result = ResultUtil.success_result(_('message_task_update_success'), {
            'sp': sp
        }).__dict__

        return JsonResponse(result)

    @room_token_required
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

@method_decorator(csrf_protect, name="dispatch")
class AddParticipantView(BaseView):
    @user_required
    def dispatch(self, request, *args, **kwargs):
        self.room_id = kwargs.get("room_id")
        self.room = Room.objects.filter(room_code=self.room_id).first()

        if self.room is None:
            result = ResultUtil.error_result(_("message_room_not_found")).__dict__

            return JsonResponse(result)

        return super().dispatch(request, *args, **kwargs)
    
    @room_token_required
    def post(self, request, *args, **kwargs):
        user = request.user
        exists = Participant.objects.filter(
            room=self.room,
            user=request.user
        ).exists()

        if exists:
            result = ResultUtil.success_result(
                None,
                {'no_need_add_participant': True}
            ).__dict__

            return JsonResponse(result)

        create_data = {
            "room": self.room,
            "user": user,
            "is_active": True,
        }
        participant = Participant.objects.create(**create_data)
        result = ResultUtil.success_result(
            _('message_room_join_success'),
            {
                **model_to_dict(participant, fields=["id", "is_active"]),
                "username": participant.user.get_username()
            }
        ).__dict__

        return JsonResponse(result)

@method_decorator(csrf_protect, name="dispatch")
class RemoveParticipantView(BaseView):
    @user_required
    def dispatch(self, request, *args, **kwargs):
        self.room_id = kwargs.get("room_id")
        self.room = Room.objects.filter(room_code=self.room_id).first()

        if self.room is None:
            result = ResultUtil.error_result(_("message_room_not_found")).__dict__

            return JsonResponse(result)

        return super().dispatch(request, *args, **kwargs)
    
    @admin_required
    def delete(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            username = data.get("name")
        except json.JSONDecodeError:
            result = ResultUtil.error_result(_("message_invalid_request")).__dict__

            return JsonResponse(result)

        if not username:
            result = ResultUtil.error_result(_("message_participant_name_required")).__dict__

            return JsonResponse(result)
        
        participant = Participant.objects.filter(
            room=self.room,
            user__username=username
        ).first()

        if participant is None:
            result = ResultUtil.error_result(
                _("message_participant_not_found")
            ).__dict__
            return JsonResponse(result, status=404)

        participant.delete()

        result = ResultUtil.success_result(_('message_room_participant_remove_success')).__dict__
        response = JsonResponse(result)

        return response

def set_language(request):
    """
    Set language preference.

    Args:
        request: Django HTTP request object.

    Returns:
        Django HTTP response object.
    """
    # In URL ?lang=tr or ?lang=en
    lang = request.GET.get("lang", settings.LANGUAGE_CODE)
    available_languages = [code for code, _ in settings.LANGUAGES]

    if lang not in available_languages:
        lang = settings.LANGUAGE_CODE

    response = HttpResponseRedirect(request.META.get("HTTP_REFERER", "/"))
    response.set_cookie(
        settings.LANGUAGE_COOKIE_NAME, 
        lang,
        httponly=True,
        samesite="Lax",
        secure=not settings.DEBUG
    )

    translation.activate(lang)

    return response

def manifest(request):
    return render(request, 'manifests/site.webmanifest', content_type='application/manifest+json')
