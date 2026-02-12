from functools import wraps
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils.translation import gettext as _
from .services import ResultUtil, RoomService

def admin_required(view_func):
    @wraps(view_func)
    def _wrapped_view(self, request, *args, **kwargs):
        if not request.user.is_authenticated or not request.user.is_staff:
            return JsonResponse(
                ResultUtil.error_result(
                    _("message_only_admin_can_perform_action")
                ).__dict__,
                status=403
            )
        return view_func(self, request, *args, **kwargs)
    return _wrapped_view

def room_not_revealed_required(view_func):
    @wraps(view_func)
    def _wrapped_view(self, request, *args, **kwargs):
        if getattr(self.room, "revealed", False):
            return JsonResponse(
                ResultUtil.error_result(
                    _("message_voting_is_closed")
                ).__dict__,
                status=403
            )
        return view_func(self, request, *args, **kwargs)
    return _wrapped_view

def room_token_required(view_func):
    @wraps(view_func)
    def _wrapped_view(self, request, *args, **kwargs):
        if request.user.is_staff or request.user.is_superuser:
            return view_func(self, request, *args, **kwargs)

        room = getattr(self, "room", None)

        if not room:
            messages.error(request, _("message_room_not_found"))

            return redirect(self.HOME_URL)

        room_service = RoomService()
        token = request.COOKIES.get("token")
        expected_token = room_service.generate_token(room.room_code, room.room_password)

        if token != expected_token:
            messages.error(request, _("message_room_access_denied"))

            return redirect(self.HOME_URL)

        return view_func(self, request, *args, **kwargs)

    return _wrapped_view
