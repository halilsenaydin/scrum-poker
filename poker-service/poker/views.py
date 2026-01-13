from django.shortcuts import render, redirect
from django.contrib import messages
from django.views.generic import TemplateView
from django.utils import translation
from django.http import HttpResponseRedirect
from django.conf import settings
from .constants import PokerConstant
from .services import RoomService


class RoomsHomeView(TemplateView):
    """
    Rooms home view.

    Args:
        TemplateView: Django TemplateView class.

    Returns:
        Renders the home.html template with room join/create functionality.
    """

    template_name = "home.html"
    HOME_URL = "poker:home"
    ROOM_URL = "poker:room"
    ACTION_HANDLERS = {
        "join_room": "handle_join_room",
        "create_room": "handle_create_room",
    }
    room_service = RoomService()

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

        return redirect(self.ROOM_URL, room_id=room_id)

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


def room_view(request, room_id):
    """
    Room view.

    Args:
        request: Django HTTP request object.
        room_id: Room identifier.

    Returns:
        Django HTTP response object.
    """
    room_service = RoomService()
    room = room_service.get_room(room_id)

    if room is None:
        messages.error(request, "Oda bulunamadı.")
        return redirect("poker:home")

    context = {
        "room_id": room_id,
        "room": room,
        "points": PokerConstant.POINTS,
    }
    return render(request, "room.html", context)


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
    response.set_cookie(settings.LANGUAGE_COOKIE_NAME, lang)

    translation.activate(lang)

    return response
