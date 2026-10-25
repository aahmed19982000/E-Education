"""Exam rules shared by the student pages and the teacher dashboard."""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from courses.models import Enrollment
from quiz.audio import AudioDecodeError, compress_audio
from quiz.models import AUDIO_MAX_MB

from .models import Answer, Exam, ExamQuestion, Submission

STATE_NOT_OPEN = "not_open"
STATE_TODO = "todo"
STATE_LATE = "late"
STATE_SUBMITTED = "submitted"  # handed in, waiting for the teacher's marks
STATE_GRADED = "graded"


def active_enrollment(user, exam):
    """The student's active place in a group at the exam's level (None: not their exam)."""
    return (Enrollment.objects.filter(user=user, cohort__level_id=exam.level_id, status=Enrollment.STATUS_ACTIVE)
            .select_related("cohort").first())


def state_for(exam, user, submission=None, now=None, cohort=None):
    """Where one student stands on one exam; `cohort` is their group (looked up when left out)."""
    now = now or timezone.now()
    if submission is None:
        submission = exam.submissions.filter(user=user).first()
    if submission is not None:
        return STATE_GRADED if submission.is_graded else STATE_SUBMITTED
    if cohort is None:
        enrollment = active_enrollment(user, exam)
        cohort = enrollment.cohort if enrollment else None
    if cohort is None or not exam.is_open(cohort, now):
        return STATE_NOT_OPEN
    deadline = exam.deadline(cohort)
    return STATE_LATE if deadline and now > deadline else STATE_TODO


def student_exams(user, now=None):
    """Published exams that are open for the student, newest first, each with their state."""
    now = now or timezone.now()
    cohorts = {e.cohort.level_id: e.cohort for e in
               Enrollment.objects.filter(user=user, status=Enrollment.STATUS_ACTIVE, cohort__level__isnull=False)
               .select_related("cohort__course")}
    exams = (Exam.objects.filter(level_id__in=cohorts, is_published=True)
             .select_related("level__course").prefetch_related("questions"))
    subs = {s.exam_id: s for s in Submission.objects.filter(user=user, exam__in=exams).prefetch_related("answers")}
    rows = []
    for exam in exams:
        cohort = cohorts[exam.level_id]
        if not exam.is_open(cohort, now) and exam.pk not in subs:
            continue
        sub = subs.get(exam.pk)
        rows.append({"exam": exam, "cohort": cohort, "submission": sub,
                     "state": state_for(exam, user, sub, now, cohort), "deadline": exam.deadline(cohort),
                     "opens_at": exam.opens_at(cohort)})
    rows.sort(key=lambda r: r["opens_at"] or now, reverse=True)
    return rows


class SubmitError(Exception):
    """A problem the student can fix (bad audio file...); the message is shown to them."""


@transaction.atomic
def submit(exam, user, post, files, cohort):
    """Save a student's answers; multiple choice is marked now, the rest waits for the teacher."""
    now = timezone.now()
    deadline = exam.deadline(cohort)
    submission = Submission.objects.create(exam=exam, user=user, cohort=cohort,
                                           is_late=bool(deadline and now > deadline))
    for question in exam.questions.all():
        key = f"q{question.pk}"
        answer = Answer(submission=submission, question=question)
        if question.kind == ExamQuestion.KIND_MCQ:
            raw = post.get(key, "")
            if raw.isdigit() and int(raw) < len(question.options):
                answer.choice_index = int(raw)
            answer.points_awarded = question.points if answer.choice_index == question.correct_index else Decimal(0)
        elif question.kind == ExamQuestion.KIND_TEXT:
            answer.text = post.get(key, "").strip()
            if not answer.text:
                answer.points_awarded = Decimal(0)  # nothing to mark
        else:
            upload = files.get(key)
            if upload:
                if upload.size > AUDIO_MAX_MB * 1024 * 1024:
                    raise SubmitError(f"ملف الصوت أكبر من {AUDIO_MAX_MB}MB.")
                try:
                    answer.audio_file = compress_audio(upload)
                except AudioDecodeError:
                    raise SubmitError("تعذّر قراءة ملف الصوت. جرّب تسجيلًا أو ملفًا آخر.")
            else:
                answer.points_awarded = Decimal(0)
        answer.save()
    submission.refresh_graded()
    return submission


def can_review(user, submission):
    """The teacher of the student's group and dashboard admins may open a submission; nobody else."""
    from dashboard.permissions import ROLE_TEACHER, get_dashboard_role
    role = get_dashboard_role(user)
    if role is None:
        return False
    if role != ROLE_TEACHER:
        return True
    profile = getattr(user, "profile", None)
    cohort = submission.cohort
    return bool(profile and profile.team_member_id and cohort and cohort.teacher_id == profile.team_member_id)
