from functools import wraps
from django.http import JsonResponse
from django.utils.translation import gettext as _
from .services import ResultUtil

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
