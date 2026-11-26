from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

admin.site.site_header = "ArtStock Admin"
admin.site.site_title = "ArtStock Admin Portal"
admin.site.index_title = "Welcome to the ArtStock portal"

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('django_prometheus.urls')),
    path('', include('stock.urls')),
]

if settings.DEBUG or settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
    ]
