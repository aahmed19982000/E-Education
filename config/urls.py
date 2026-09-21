from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('core.urls')),
    path('levels/', include('levels.urls')),
    path('articles/', include('articles.urls')),
    path('test/', include('quiz.urls')),
    path('accounts/', include('accounts.urls')),
    path('contact/', include('contact_us.urls')),
    path('dashboard/', include('dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
