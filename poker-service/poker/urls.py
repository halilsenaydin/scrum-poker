from django.urls import path
from . import views

app_name = "poker"

urlpatterns = [
    path("", views.RoomsHomeView.as_view(), name="home"),
    path("room/<str:room_id>/", views.RoomView.as_view(), name="room"),
    path("room/<str:room_id>/add-participant/", views.AddParticipantView.as_view(), name="add_participant"),
    path("room/<str:room_id>/remove-participant/", views.RemoveParticipantView.as_view(), name="remove_participant"),
    path("room/<str:room_id>/sprints/", views.SprintsView.as_view(), name="sprints"),
    path("room/<str:room_id>/sprints/<str:sprint_id>/tasks/", views.TaskView.as_view(), name="tasks"),
    path("room/<str:room_id>/sprints/<str:sprint_id>/tasks/<str:task_id>/", views.TaskDetailView.as_view(), name="task_detail"),
    path('set-language/', views.set_language, name='set_language'),
    path('site.webmanifest', views.manifest, name='manifest'),
]
