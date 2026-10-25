from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.urls import include, path

from core.seo import SITEMAPS, robots_txt

urlpatterns = [
    path('admin/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': SITEMAPS}, name='sitemap'),
    path('robots.txt', robots_txt, name='robots'),
    path('', include('core.urls')),
    path('articles/', include('articles.urls')),
    path('team/', include('team.urls')),
    path('courses/', include('courses.urls')),
    path('exams/', include('exams.urls')),
    path('test/', include('quiz.urls')),
    path('accounts/', include('accounts.urls')),
    path('contact/', include('contact_us.urls')),
    path('dashboard/', include('dashboard.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
