from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("", views.index, name="index"),

    path("levels/", views.levels_list, name="levels_list"),
    path("levels/add/", views.level_form, name="level_create"),
    path("levels/<int:pk>/edit/", views.level_form, name="level_edit"),
    path("levels/<int:pk>/delete/", views.level_delete, name="level_delete"),

    path("articles/", views.articles_list, name="articles_list"),
    path("articles/add/", views.article_form, name="article_create"),
    path("articles/<int:pk>/edit/", views.article_form, name="article_edit"),
    path("articles/<int:pk>/delete/", views.article_delete, name="article_delete"),

    path("team/", views.team_list, name="team_list"),
    path("team/add/", views.team_form, name="team_create"),
    path("team/<int:pk>/edit/", views.team_form, name="team_edit"),
    path("team/<int:pk>/delete/", views.team_delete, name="team_delete"),

    path("questions/", views.questions_list, name="questions_list"),
    path("questions/categories/", views.categories_list, name="categories_list"),
    path("questions/categories/add/", views.category_form, name="category_create"),
    path("questions/categories/quick-add/", views.category_quick_add, name="category_quick_add"),
    path("questions/categories/<int:pk>/edit/", views.category_form, name="category_edit"),
    path("questions/categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("questions/placement/", views.quiz_placement, name="quiz_placement"),
    path("questions/grading/", views.quiz_grading, name="quiz_grading"),
    path("questions/reorder/", views.questions_reorder, name="questions_reorder"),
    path("questions/add/", views.question_form, name="question_create"),
    path("questions/<int:pk>/edit/", views.question_form, name="question_edit"),
    path("questions/<int:pk>/delete/", views.question_delete, name="question_delete"),

    path("messages/", views.messages_list, name="messages_list"),
    path("messages/<int:pk>/", views.message_detail, name="message_detail"),
    path("messages/<int:pk>/delete/", views.message_delete, name="message_delete"),

    path("users/", views.users_list, name="users_list"),
    path("users/add/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
]
