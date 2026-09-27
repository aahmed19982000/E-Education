"""A student's run through the level test, kept in the session.

The server is the source of truth for time: the page only shows countdowns.
Time a question is on screen is added to that question's budget on every
request ("tick"), so refreshing or navigating away can't reset a timer, and
answers arriving after a question's or the exam's time are ignored.
"""
import time

from .models import Question, QuizSettings

SESSION_KEY = "quiz_attempt"
GRACE_SECONDS = 3  # network latency allowance for an answer sent as time runs out


class Attempt:
    def __init__(self, request, data):
        self.request = request
        self.data = data
        self.settings = QuizSettings.load()
        by_pk = Question.objects.select_related("category").in_bulk(data["question_ids"])
        # Questions deleted mid-attempt simply drop out.
        self.questions = [by_pk[pk] for pk in data["question_ids"] if pk in by_pk]

    # --- lifecycle ---------------------------------------------------------

    @classmethod
    def start(cls, request):
        settings = QuizSettings.load()
        now = time.time()
        request.session[SESSION_KEY] = {
            "question_ids": list(Question.objects.values_list("pk", flat=True)),
            "started_at": now,
            "deadline": now + settings.exam_time_minutes * 60 if settings.exam_time_minutes else None,
            "index": 0,
            "answers": {},       # str(pk) -> chosen option index
            "spent": {},         # str(pk) -> seconds the question has been on screen
            "current": None,     # pk on screen, and since when
            "shown_at": None,
            "finished": False,
        }
        return cls(request, request.session[SESSION_KEY])

    @classmethod
    def load(cls, request):
        data = request.session.get(SESSION_KEY)
        return cls(request, data) if data else None

    def save(self):
        self.request.session[SESSION_KEY] = self.data
        self.request.session.modified = True

    # --- time --------------------------------------------------------------

    def tick(self, now=None):
        """Charge the time since the last request to the question that was on screen."""
        now = now or time.time()
        current, shown_at = self.data["current"], self.data["shown_at"]
        if current is not None and shown_at is not None:
            key = str(current)
            self.data["spent"][key] = self.data["spent"].get(key, 0) + max(0, now - shown_at)
        self.data["shown_at"] = now if current is not None else None

    def show(self, question, now=None):
        self.data["current"] = question.pk
        self.data["shown_at"] = now or time.time()

    def exam_remaining(self, now=None):
        deadline = self.data["deadline"]
        if deadline is None:
            return None
        return max(0, deadline - (now or time.time()))

    def exam_expired(self, now=None):
        remaining = self.exam_remaining(now)
        return remaining is not None and remaining <= 0

    def question_limit(self, question):
        return self.settings.question_limit(question)

    def question_remaining(self, question):
        limit = self.question_limit(question)
        if limit is None:
            return None
        return max(0, limit - self.data["spent"].get(str(question.pk), 0))

    def question_locked(self, question, grace=0):
        limit = self.question_limit(question)
        return limit is not None and self.data["spent"].get(str(question.pk), 0) > limit + grace

    # --- answers & navigation ---------------------------------------------

    @property
    def finished(self):
        return self.data["finished"]

    @property
    def index(self):
        return min(self.data["index"], max(len(self.questions) - 1, 0))

    def current_question(self):
        return self.questions[self.index] if self.questions else None

    def answer(self, question, option):
        """Record a choice unless the question's or the exam's time is up."""
        if self.finished or self.question_locked(question, GRACE_SECONDS):
            return False
        deadline = self.data["deadline"]
        if deadline is not None and time.time() > deadline + GRACE_SECONDS:
            return False
        if not 0 <= option < len(question.options_ar):
            return False
        self.data["answers"][str(question.pk)] = option
        return True

    def chosen(self, question):
        return self.data["answers"].get(str(question.pk))

    def go(self, index):
        self.data["index"] = max(0, min(index, len(self.questions) - 1))

    def finish(self):
        self.data["finished"] = True
        self.data["current"] = None
        self.data["shown_at"] = None

    def results(self):
        """{question pk: answered correctly} for grading."""
        return {q.pk: self.chosen(q) == q.correct_index for q in self.questions}

    def unanswered_count(self):
        return sum(1 for q in self.questions if self.chosen(q) is None)
