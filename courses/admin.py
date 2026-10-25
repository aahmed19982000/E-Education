from django.contrib import admin

from .models import Certificate, Payment

admin.site.register(Certificate)
admin.site.register(Payment)
