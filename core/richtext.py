"""Tiny allow-list HTML sanitiser for article bodies written in the dashboard editor."""
from html import escape
from html.parser import HTMLParser

from django.utils.html import linebreaks
from django.utils.safestring import mark_safe

ALLOWED = {"p", "br", "strong", "b", "em", "i", "u", "h2", "h3", "ul", "ol", "li", "a", "blockquote"}
VOID = {"br"}
SAFE_SCHEMES = ("http://", "https://", "mailto:", "/")


class _Cleaner(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.out = []
        self.open = []

    def handle_starttag(self, tag, attrs):
        if tag not in ALLOWED:
            return
        if tag == "a":
            href = dict(attrs).get("href") or ""
            if not href.strip().lower().startswith(SAFE_SCHEMES):
                self.open.append(None)
                return
            self.out.append(f'<a href="{escape(href.strip(), quote=True)}" rel="noopener nofollow" target="_blank">')
        else:
            self.out.append(f"<{tag}>")
        if tag not in VOID:
            self.open.append(tag)

    def handle_endtag(self, tag):
        if tag not in ALLOWED or tag in VOID:
            return
        while self.open:
            last = self.open.pop()
            if last is None:
                continue
            self.out.append(f"</{last}>")
            if last == tag:
                break

    def handle_data(self, data):
        self.out.append(escape(data))

    def result(self):
        while self.open:
            last = self.open.pop()
            if last:
                self.out.append(f"</{last}>")
        return "".join(self.out)


def clean_html(text):
    parser = _Cleaner()
    parser.feed(text or "")
    parser.close()
    return parser.result()


def render_body(text):
    """Safe HTML for a body: sanitised if it holds markup, plain paragraphs otherwise."""
    text = text or ""
    if "<" in text and ">" in text:
        return mark_safe(clean_html(text))
    return mark_safe(linebreaks(escape(text)))
