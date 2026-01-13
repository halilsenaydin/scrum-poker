from django.urls import path
from . import views

app_name = "poker"

urlpatterns = [
    path("", views.RoomsHomeView.as_view(), name="home"),
    path("room/<str:room_id>/", views.room_view, name="room"),
    path('set-language/', views.set_language, name='set_language'),
]
