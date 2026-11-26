from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "ArtStock Admin"
admin.site.site_title = "ArtStock Admin Portal"
admin.site.index_title = "Welcome to the ArtStock portal"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('django_prometheus.urls')),
    path('', include('stock.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
