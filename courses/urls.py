from django.urls import path

from . import views

app_name = "courses"

urlpatterns = [
    path("", views.course_list, name="list"),
    path("mine/", views.my_courses, name="mine"),
    path("lesson/<int:pk>/", views.lesson_detail, name="lesson"),
    path("attachment/<int:pk>/", views.attachment_download, name="attachment"),
    path("checkout/<int:pk>/", views.checkout, name="checkout"),
    path("checkout/<int:pk>/pay/", views.pay, name="pay"),
    path("payments/webhook/", views.payment_webhook, name="payment_webhook"),
    path("payments/mock/<str:reference>/", views.pay_mock, name="pay_mock"),
    path("certificate/<str:code>/", views.certificate, name="certificate"),
    path("certificate/<str:code>/verify/", views.verify_certificate, name="verify_certificate"),
    path("<str:slug>/apply/", views.apply, name="apply"),
    path("<str:slug>/", views.course_detail, name="detail"),
]
