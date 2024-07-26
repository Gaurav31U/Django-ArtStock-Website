from django.utils.cache import add_never_cache_headers

class NoCacheForMetricsMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path == '/metrics':
            add_never_cache_headers(response)
        return response
