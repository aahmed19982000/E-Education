from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("about/", views.about, name="about"),
    path("teachers/", views.teachers, name="teachers"),
    path("lang/<str:lang_code>/", views.set_language, name="set_language"),
]
