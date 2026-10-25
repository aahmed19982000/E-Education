"""Emails to students, teachers and staff (bilingual: Arabic first, English underneath).

Nothing here may break the action that triggered it: a failed send is logged and ignored.
Without EMAIL_HOST the emails are printed to the console instead of being sent.
"""
import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import NotificationLog

log = logging.getLogger(__name__)


def absolute(path):
    return f"{settings.SITE_URL}{path}"


def _body(ar, en, link=None):
    parts = [ar, "", "—", "", en]
    if link:
        parts += ["", link]
    parts += ["", "أكاديمية E-Education · E-Education Academy"]
    return "\n".join(parts)


def send(to, subject_ar, subject_en, body_ar, body_en, link=None, once=None):
    """Send one email. `once=(kind, key)` makes it idempotent per recipient. Returns True if sent."""
    to = [a for a in ([to] if isinstance(to, str) else to) if a]
    sent_any = False
    for address in to:
        if once:
            try:
                with transaction.atomic():
                    NotificationLog.objects.create(kind=once[0], key=once[1], email=address)
            except IntegrityError:
                continue
        try:
            msg = EmailMultiAlternatives(f"{subject_ar} | {subject_en}", _body(body_ar, body_en, link),
                                         settings.DEFAULT_FROM_EMAIL, [address])
            msg.send()
            sent_any = True
        except Exception:  # noqa: BLE001 - a mail problem must never break enrolment, payment, etc.
            log.exception("Could not send email to %s", address)
            if once:
                NotificationLog.objects.filter(kind=once[0], key=once[1], email=address).delete()
    return sent_any


def _fmt(dt):
    return timezone.localtime(dt).strftime("%Y-%m-%d %H:%M")


def request_received(req):
    """Student: we got your request. Staff: a new request arrived."""
    course = req.course.title_ar if req.course else "ورشة المدرسين"
    course_en = (req.course.title_en or req.course.title_ar) if req.course else "Teachers workshop"
    send(req.email, "استلمنا طلب اشتراكك", "We received your request",
         f"أهلًا {req.full_name}، استلمنا طلبك في «{course}». سيتواصل معك فريقنا قريبًا لتأكيد التفاصيل.",
         f"Hi {req.full_name}, we received your request for \"{course_en}\". Our team will contact you shortly.",
         once=("request", f"req:{req.pk}"))
    if settings.ADMIN_NOTIFY_EMAIL:
        send(settings.ADMIN_NOTIFY_EMAIL, "طلب اشتراك جديد", "New enrollment request",
             f"{req.full_name} ({req.phone}) طلب الاشتراك في «{course}».",
             f"{req.full_name} ({req.phone}) requested \"{course_en}\".",
             link=absolute(f"/dashboard/requests/{req.pk}/"), once=("request", f"req:{req.pk}"))


def payment_received(req):
    course = req.course.title_ar if req.course else "ورشة المدرسين"
    course_en = (req.course.title_en or req.course.title_ar) if req.course else "Teachers workshop"
    send(req.email, "تم استلام الدفع", "Payment received",
         f"شكرًا {req.full_name}، تم استلام دفعتك لـ«{course}». سنختار معك المدرس والمواعيد ثم نؤكد التسجيل.",
         f"Thank you {req.full_name}, we received your payment for \"{course_en}\". We will agree the teacher and times with you next.",
         link=absolute("/test/"), once=("payment", f"req:{req.pk}"))
    if settings.ADMIN_NOTIFY_EMAIL:
        send(settings.ADMIN_NOTIFY_EMAIL, "دفعة جديدة", "New payment",
             f"{req.full_name} دفع لـ«{course}».", f"{req.full_name} paid for \"{course_en}\".",
             link=absolute(f"/dashboard/requests/{req.pk}/"), once=("payment", f"req:{req.pk}"))


def enrolled(user, cohort):
    """Student: you are in a group; here is when it starts."""
    when = f"تبدأ الجلسات في {cohort.start_date:%Y-%m-%d}." if cohort.start_date else "سنرسل لك موعد أول جلسة."
    when_en = f"Sessions start on {cohort.start_date:%Y-%m-%d}." if cohort.start_date else "We will send you the first session time."
    send(user.email, "تم تسجيلك في الكورس", "You are enrolled",
         f"تم تسجيلك في «{cohort.course.title_ar}». {when} ستجد جلساتك في لوحتك.",
         f"You are enrolled in \"{cohort.course.title_en or cohort.course.title_ar}\". {when_en} Your sessions are in your dashboard.",
         link=absolute("/courses/mine/"), once=("enrolled", f"cohort:{cohort.pk}:user:{user.pk}"))


def lesson_reminder(lesson, user, teacher=False):
    title = lesson.cohort.course.title_ar
    link = absolute("/dashboard/" if teacher else f"/courses/lesson/{lesson.pk}/")
    send(user.email, "تذكير بجلسة قريبة", "Session reminder",
         f"تذكير: جلسة «{title}» رقم {lesson.number} تبدأ {_fmt(lesson.starts_at)}.",
         f"Reminder: session {lesson.number} of \"{lesson.cohort.course.title_en or title}\" starts {_fmt(lesson.starts_at)}.",
         link=link, once=("lesson_reminder", f"lesson:{lesson.pk}"))


def exam_due(exam, user, deadline):
    send(user.email, "تذكير بامتحان", "Exam reminder",
         f"امتحان «{exam.display_title}» ينتهي موعده {_fmt(deadline)}. لا تنسَ تسليمه.",
         f"Your exam \"{exam.display_title}\" is due {_fmt(deadline)}. Don't forget to submit it.",
         link=absolute(f"/exams/{exam.pk}/"), once=("exam_due", f"exam:{exam.pk}"))


def certificate_issued(cert):
    send(cert.enrollment.user.email, "شهادة إتمام المستوى جاهزة", "Your completion certificate is ready",
         f"مبروك! حصلت على شهادة إتمام «{cert.enrollment.course.title_ar}» بنسبة {cert.final_percent}%.",
         f"Congratulations! You earned your \"{cert.enrollment.course.title_en or cert.enrollment.course.title_ar}\" certificate with {cert.final_percent}%.",
         link=absolute(f"/courses/certificate/{cert.code}/"), once=("certificate", f"cert:{cert.pk}"))
