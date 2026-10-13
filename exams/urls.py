from django.urls import path

from . import views

app_name = "exams"

urlpatterns = [
    path("<int:pk>/", views.take, name="take"),
    path("answer/<int:pk>/audio/", views.answer_audio, name="audio"),
]
