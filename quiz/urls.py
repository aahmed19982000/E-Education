from django.urls import path

from . import views

app_name = "quiz"

urlpatterns = [
    path("", views.intro, name="intro"),
    path("start/", views.start, name="start"),
    path("question/", views.question, name="question"),
    path("result/", views.result, name="result"),
]
