"""Write all of an exam's questions in one text box instead of one form per question.

    What is the past tense of "go"?   [2]
    - goed
    + went
    - gone

    Write a sentence about your day.  [3]

    [voice] Say your name and where you live.

Questions are separated by a blank line. A question with `-` / `+` lines under it is multiple choice
(`+` marks the right answer); without them it is a written answer, or a spoken one when it starts with
[voice] / [صوت]. `[2]` at the end of the question line is its marks (1 when left out). A leading
"1." / "1)" is ignored. `parse` reads the text, `dump` turns saved questions back into it so editing
is just editing the text.
"""
import re
from decimal import Decimal, InvalidOperation

from .models import ExamQuestion

CORRECT = ("+", "*", "✓", "✔")
OPTION = re.compile(r"^\s*([-•+*✓✔])\s*(.+?)\s*$")
LETTERED = re.compile(r"^\s*\(?[A-Da-d]\)\s+([+*✓✔]?)\s*(.+?)\s*$")
POINTS = re.compile(r"\s*\[\s*(\d+(?:[.,]\d+)?)\s*\]\s*$")
NUMBERING = re.compile(r"^\s*\d+\s*[.)\-:]\s+")
VOICE = re.compile(r"^\s*\[\s*(voice|صوت|صوتي)\s*\]\s*", re.I)
WRITTEN = re.compile(r"^\s*\[\s*(text|written|كتابة|كتابي)\s*\]\s*", re.I)


class BulkError(Exception):
    """One message per problem, each saying which question it is about."""

    def __init__(self, errors):
        super().__init__("\n".join(errors))
        self.errors = errors


def _option(line):
    m = LETTERED.match(line)
    if m:
        return m.group(2), bool(m.group(1))
    m = OPTION.match(line)
    if m:
        return m.group(2), m.group(1) in CORRECT
    return None


def parse(text):
    """Return a list of {"kind", "text", "points", "options", "correct_index"}; raise BulkError."""
    blocks = [b for b in re.split(r"\n\s*\n", (text or "").replace("\r\n", "\n").strip()) if b.strip()]
    questions, errors = [], []
    for n, block in enumerate(blocks, 1):
        lines = [l for l in block.split("\n") if l.strip()]
        head, options, correct, stem_done = [], [], [], False
        for line in lines:
            opt = _option(line) if (head or stem_done) else None
            if opt:
                stem_done = True
                options.append(opt[0])
                if opt[1]:
                    correct.append(len(options) - 1)
            elif stem_done:
                errors.append(f"السؤال {n}: السطر «{line.strip()}» لازم يبدأ بـ - أو + لأنه تحت الاختيارات.")
            else:
                head.append(line.strip())
        stem = " ".join(head)
        points = Decimal(1)
        m = POINTS.search(stem)
        if m:
            try:
                points = Decimal(m.group(1).replace(",", "."))
            except InvalidOperation:
                pass
            stem = stem[:m.start()].rstrip()
        kind = ExamQuestion.KIND_MCQ if options else ExamQuestion.KIND_TEXT
        if not options:
            if VOICE.match(stem):
                kind, stem = ExamQuestion.KIND_VOICE, VOICE.sub("", stem)
            elif WRITTEN.match(stem):
                stem = WRITTEN.sub("", stem)
        stem = NUMBERING.sub("", stem).strip()
        if not stem:
            errors.append(f"السؤال {n}: نص السؤال فارغ.")
            continue
        if options and len(options) < 2:
            errors.append(f"السؤال {n}: أضف اختيارين على الأقل.")
        elif options and len(correct) != 1:
            errors.append(f"السؤال {n}: علّم إجابة صحيحة واحدة بالرمز + (وجدت {len(correct)}).")
        questions.append({"kind": kind, "text": stem, "points": points, "options": options,
                          "correct_index": correct[0] if len(correct) == 1 else None})
    if errors:
        raise BulkError(errors)
    return questions


def dump(exam):
    """The saved questions as the same text `parse` reads."""
    blocks = []
    for q in exam.questions.all():
        mark = f"  [{q.points.normalize():f}]" if q.points != 1 else ""
        if q.kind == ExamQuestion.KIND_MCQ:
            rows = [f"{'+' if i == q.correct_index else '-'} {o}" for i, o in enumerate(q.options)]
            blocks.append("\n".join([q.text + mark] + rows))
        elif q.kind == ExamQuestion.KIND_VOICE:
            blocks.append(f"[صوت] {q.text}{mark}")
        else:
            blocks.append(q.text + mark)
    return "\n\n".join(blocks)


def apply(exam, parsed):
    """Make the exam's questions match `parsed`, keeping a question (and the answers handed in for it)
    when it stays in the same position. Removing questions that students already answered is refused."""
    existing = list(exam.questions.all())
    if len(parsed) < len(existing) and any(q.answers.exists() for q in existing[len(parsed):]):
        raise BulkError(["لا يمكن حذف أسئلة أجاب عنها الطلاب بالفعل. عدّل نصها أو اتركها."])
    for i, data in enumerate(parsed):
        if i < len(existing):
            q = existing[i]
        else:
            q = ExamQuestion(exam=exam)
        q.order = i + 1
        q.kind, q.text, q.points = data["kind"], data["text"], data["points"]
        q.options, q.correct_index = data["options"], data["correct_index"]
        q.save()
        if i < len(existing) and q.is_auto:  # an edited right answer re-marks what was already handed in
            for a in q.answers.all():
                a.points_awarded = q.points if a.choice_index == q.correct_index else Decimal(0)
                a.save(update_fields=["points_awarded"])
    for q in existing[len(parsed):]:
        q.delete()
