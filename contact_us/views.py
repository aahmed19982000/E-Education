from django.shortcuts import render

from .forms import ContactForm


def contact_view(request):
    submitted = False
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            submitted = True
            form = ContactForm()
    else:
        form = ContactForm()

    return render(request, "contact_us/contact.html", {
        "form": form,
        "submitted": submitted,
    })
