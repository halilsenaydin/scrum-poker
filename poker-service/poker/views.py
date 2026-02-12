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
from .models import Room, Participant, TaskVote, Task
from .services import RoomService, ResultUtil
from .decorators import admin_required, room_not_revealed_required, room_token_required

class BaseView(View):
    # Page Urls
    HOME_URL = "poker:home"
    ROOM_URL = "poker:room"
    TASK_DETAIL_URL = "poker:task_detail"
    TASKS_URL = "poker:tasks"

    # Cookie Keys
    COOKIE_AUTHENTICATION_KEY = "authentication_key"
    COOKIE_ROOM_STATE = "room_state"
    COOKIE_TOKEN = "token"

    room_service = RoomService()

    def _get_task_from_cookies(self, context):
        room_state_raw = self.request.COOKIES.get(self.COOKIE_ROOM_STATE)
        task_id = context.get("task_id")

        if not room_state_raw or not task_id:
            return None

        try:
            room_state = json.loads(room_state_raw)
        except json.JSONDecodeError:
            return None

        task_data = room_state.get("tasks", {}).get(str(task_id), {})    

        return task_data 
        
    def _get_selected_vote_from_cookies(self, context):
        task_data = self._get_task_from_cookies(context)

        return task_data.get("vote") if task_data else None

    def _get_authentication_key_from_cookies(self):
        authentication_key = self.request.COOKIES.get(self.COOKIE_AUTHENTICATION_KEY)

        return authentication_key

class BaseTemplateView(BaseView, TemplateView):
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

class TaskView(BaseTemplateView):
    template_name = "tasks.html"

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
        tasks = (
            self.room.tasks
            .filter(is_active=True)
        )
        participants = (
            self.room.participants
            .filter(is_active=True)
        )
        user = self.request.user
        is_admin = user.is_authenticated and user.is_staff
        authentication_key = self._get_authentication_key_from_cookies()

        context.update({
            "authentication_key": authentication_key,
            "is_admin": is_admin,
            "tasks": tasks,
            "room_id": self.room_id,
            "room_name": self.room.name,
            "participants": participants,
            "revealed": self.room.revealed
        })

        return context

    @room_token_required
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

@method_decorator(csrf_protect, name="dispatch")
class TaskDetailView(BaseTemplateView):
    template_name = "task_detail.html"
    
    def dispatch(self, request, *args, **kwargs):
        self.room = Room.objects.filter(
            room_code=kwargs.get("room_id")
        ).first()

        if not self.room:
            messages.error(request, _("message_room_not_found"))
            return redirect(self.HOME_URL)

        self.task = self.room.tasks.filter(
            id=kwargs.get("task_id"),
            is_active=True
        ).first()

        if not self.task:
            messages.error(request, _("message_task_not_found"))

            return redirect(self.TASKS_URL, room_id=self.room.room_code)

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
        is_admin = user.is_authenticated and user.is_staff
        room_revealed = self.room.revealed
        authentication_key = self._get_authentication_key_from_cookies()

        context.update({
            "authentication_key": authentication_key,
            "revealed": self.room.revealed,
            "room_id": self.kwargs["room_id"],
            "room_name": self.room.name,
            "task_id": self.kwargs["task_id"],
            "points": PokerConstant.POINTS,
            "selected_vote": self._get_selected_vote_from_cookies(context),
            "participants": participants,
            "is_admin": is_admin,
            "task": self.task,
            "metrics": self.task.metrics if room_revealed or is_admin else None,
            "show_vote_display": True
        })

        return context

    @room_not_revealed_required
    def post(self, request, *args, **kwargs):
        auth_key = request.COOKIES.get(self.COOKIE_AUTHENTICATION_KEY)

        if not auth_key:
            result = ResultUtil.error_result(_('message_auth_key_not_found')).__dict__

            return JsonResponse(result, status=401)

        room_id = kwargs["room_id"]
        task_id = kwargs["task_id"]
        data = json.loads(request.body)
        vote = data.get("vote")

        # Current room state
        room_state_raw = request.COOKIES.get(self.COOKIE_ROOM_STATE)

        if room_state_raw:
            try:
                room_state = json.loads(room_state_raw)
            except json.JSONDecodeError:
                room_state = None
        else:
            room_state = None

        # Set room state if not exist currently on cookie
        if not room_state or room_state.get("room_id") != room_id:
            room_state = {
                "room_id": room_id,
                "tasks": {}
            }

        # Update task state
        room_state["tasks"][task_id] = {
            "vote": vote
        }

        result = ResultUtil.success_result(_('message_vote_success'), {
            "vote": vote
        }).__dict__
        response = JsonResponse(result)
        response.set_cookie(
            self.COOKIE_ROOM_STATE,
            json.dumps(room_state),
            httponly=True,
            samesite="Lax",
            secure=not settings.DEBUG
        )

        try:
            participant = Participant.objects.get(
                authentication_key=auth_key,
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

        return response
    
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
    def dispatch(self, request, *args, **kwargs):
        self.room_id = kwargs.get("room_id")
        self.room = Room.objects.filter(room_code=self.room_id).first()

        if self.room is None:
            result = ResultUtil.error_result(_("message_room_not_found")).__dict__

            return JsonResponse(result)

        return super().dispatch(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        try:
            data = json.loads(request.body)
            name = data.get("name")
        except json.JSONDecodeError:
            result = ResultUtil.error_result(_("message_invalid_request")).__dict__

            return JsonResponse(result)

        if not name:
            result = ResultUtil.error_result(_("message_participant_name_required")).__dict__

            return JsonResponse(result)

        exists = Participant.objects.filter(
            room=self.room,
            name=name
        ).exists()
        authentication_key = self._get_authentication_key_from_cookies()

        if exists:
            user_exists = Participant.objects.filter(
                room=self.room,
                name=name,
                authentication_key=authentication_key
            ).exists()

            if user_exists:
                result = ResultUtil.success_result(
                    None,
                    {'no_need_add_participant': True}
                ).__dict__

                return JsonResponse(result)

            result = ResultUtil.error_result(
                _("message_participant_already_exists")
            ).__dict__

            return JsonResponse(result, status=409)

        create_data = {
            "room": self.room,
            "name": name,
            "is_active": True,
        }

        if authentication_key is not None:
            create_data["authentication_key"] = authentication_key

        participant = Participant.objects.create(**create_data)
        result = ResultUtil.success_result(_('message_room_join_success'), model_to_dict(participant, fields=["id", "name", "is_active"])).__dict__
        response = JsonResponse(result)
        response.set_cookie(
            self.COOKIE_AUTHENTICATION_KEY, 
            participant.authentication_key,
            httponly=True,
            samesite="Lax",
            secure=not settings.DEBUG
        )

        return response

@method_decorator(csrf_protect, name="dispatch")
class RemoveParticipantView(BaseView):
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
            name = data.get("name")
        except json.JSONDecodeError:
            result = ResultUtil.error_result(_("message_invalid_request")).__dict__

            return JsonResponse(result)

        if not name:
            result = ResultUtil.error_result(_("message_participant_name_required")).__dict__

            return JsonResponse(result)
        
        participant = Participant.objects.filter(
            room=self.room,
            name=name
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
