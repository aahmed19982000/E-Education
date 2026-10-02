from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.course_list, name="list"),
    path("mine/", views.my_courses, name="mine"),
    path("lesson/<int:pk>/", views.lesson_detail, name="lesson"),
    path("attachment/<int:pk>/", views.attachment_download, name="attachment"),
    path("checkout/<int:pk>/", views.checkout, name="checkout"),
    path("<slug:slug>/apply/", views.apply, name="apply"),
    path("<slug:slug>/", views.course_detail, name="detail"),
]
