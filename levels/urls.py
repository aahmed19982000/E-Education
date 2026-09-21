from django.urls import path

from . import views

app_name = "levels"

urlpatterns = [
    path("", views.levels_view, name="levels"),
]
