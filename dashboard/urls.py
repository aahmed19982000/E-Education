from django.urls import path

from . import exam_views, teacher as views_teacher, views

app_name = "dashboard"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),

    path("", views.index, name="index"),


    path("teacher/schedule/", views_teacher.teacher_schedule, name="teacher_schedule"),
    path("teacher/students/", views_teacher.teacher_students, name="teacher_students"),
    path("teacher/lessons/<int:pk>/", views_teacher.teacher_lesson, name="teacher_lesson"),
    path("teacher/lessons/<int:pk>/attendance/", views_teacher.teacher_attendance, name="teacher_attendance"),

    path("exams/", exam_views.exams_list, name="exams_list"),
    path("exams/course/<int:course_pk>/levels/", exam_views.course_levels, name="course_levels"),
    path("exams/level/<int:level_pk>/session/<int:number>/", exam_views.exam_for_session, name="exam_for_session"),
    path("exams/level/<int:level_pk>/final/", exam_views.exam_for_final, name="exam_for_final"),
    path("exams/<int:exam_pk>/questions/add/", exam_views.exam_question_form, name="exam_question_create"),
    path("exams/<int:exam_pk>/questions/reorder/", exam_views.exam_questions_reorder, name="exam_questions_reorder"),
    path("exams/questions/<int:pk>/edit/", exam_views.exam_question_form, name="exam_question_edit"),
    path("exams/questions/<int:pk>/delete/", exam_views.exam_question_delete, name="exam_question_delete"),
    path("exams/<int:pk>/results/", exam_views.exam_results, name="exam_results"),
    path("exams/submissions/<int:pk>/", exam_views.submission_grade, name="submission_grade"),

    path("settings/", views.site_settings, name="site_settings"),
    path("articles/", views.articles_list, name="articles_list"),
    path("articles/add/", views.article_form, name="article_create"),
    path("articles/<int:pk>/edit/", views.article_form, name="article_edit"),
    path("articles/<int:pk>/delete/", views.article_delete, name="article_delete"),

    path("team/", views.team_list, name="team_list"),
    path("team/<int:pk>/", views.team_profile, name="team_profile"),
    path("team/add/", views.team_form, name="team_create"),
    path("team/<int:pk>/edit/", views.team_form, name="team_edit"),
    path("team/<int:pk>/delete/", views.team_delete, name="team_delete"),
    path("team/<int:member_pk>/reviews/", views.review_list, name="review_list"),
    path("team/<int:member_pk>/reviews/add/", views.review_form, name="review_create"),
    path("team/<int:member_pk>/reviews/<int:pk>/edit/", views.review_form, name="review_edit"),
    path("team/<int:member_pk>/reviews/<int:pk>/delete/", views.review_delete, name="review_delete"),

    path("questions/", views.questions_list, name="questions_list"),
    path("questions/categories/", views.categories_list, name="categories_list"),
    path("questions/categories/add/", views.category_form, name="category_create"),
    path("questions/categories/quick-add/", views.category_quick_add, name="category_quick_add"),
    path("questions/categories/<int:pk>/edit/", views.category_form, name="category_edit"),
    path("questions/categories/<int:pk>/delete/", views.category_delete, name="category_delete"),
    path("questions/grading/", views.quiz_grading, name="quiz_grading"),
    path("questions/reorder/", views.questions_reorder, name="questions_reorder"),
    path("questions/add/", views.question_form, name="question_create"),
    path("questions/<int:pk>/edit/", views.question_form, name="question_edit"),
    path("questions/<int:pk>/delete/", views.question_delete, name="question_delete"),

    path("requests/", views.requests_list, name="requests_list"),
    path("requests/<int:pk>/", views.request_detail, name="request_detail"),
    path("requests/<int:pk>/create-account/", views.request_create_account, name="request_create_account"),
    path("requests/<int:pk>/enroll/", views.request_enroll, name="request_enroll"),
    path("cohorts/", views.all_cohorts, name="all_cohorts"),
    path("cohorts/<int:pk>/", views.cohort_detail, name="cohort_detail"),
    path("students/action/", views.student_action, name="student_action"),
    path("students/<int:user_pk>/", views.student_detail, name="student_detail"),
    path("courses/", views.courses_list, name="courses_list"),
    path("courses/add/", views.course_form, name="course_create"),
    path("courses/<int:pk>/edit/", views.course_form, name="course_edit"),
    path("courses/<int:pk>/delete/", views.course_delete, name="course_delete"),
    path("courses/<int:course_pk>/cohorts/", views.cohorts_list, name="cohorts_list"),
    path("courses/<int:course_pk>/cohorts/add/", views.cohort_form, name="cohort_create"),
    path("courses/<int:course_pk>/cohorts/<int:pk>/edit/", views.cohort_form, name="cohort_edit"),
    path("courses/<int:course_pk>/cohorts/<int:pk>/confirm/", views.cohort_confirm, name="cohort_confirm"),
    path("courses/<int:course_pk>/cohorts/<int:pk>/delete/", views.cohort_delete, name="cohort_delete"),
    path("cohorts/<int:cohort_pk>/lessons/", views.lessons_list, name="lessons_list"),
    path("cohorts/<int:cohort_pk>/lessons/generate/", views.lessons_generate, name="lessons_generate"),
    path("cohorts/<int:cohort_pk>/lessons/add/", views.lesson_form, name="lesson_create"),
    path("cohorts/<int:cohort_pk>/lessons/<int:pk>/edit/", views.lesson_form, name="lesson_edit"),
    path("cohorts/<int:cohort_pk>/lessons/<int:pk>/delete/", views.lesson_delete, name="lesson_delete"),
    path("cohorts/<int:cohort_pk>/lessons/<int:pk>/attendance/", views.attendance_form, name="attendance_form"),
    path("courses/<int:course_pk>/students/", views.enrollments_list, name="enrollments_list"),
    path("courses/<int:course_pk>/students/<int:pk>/<str:action>/", views.enrollment_action, name="enrollment_action"),

    path("messages/", views.messages_list, name="messages_list"),
    path("messages/<int:pk>/", views.message_detail, name="message_detail"),
    path("messages/<int:pk>/delete/", views.message_delete, name="message_delete"),

    path("users/", views.users_list, name="users_list"),
    path("users/add/", views.user_create, name="user_create"),
    path("users/<int:pk>/edit/", views.user_edit, name="user_edit"),
]
