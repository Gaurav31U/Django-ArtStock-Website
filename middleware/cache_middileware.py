from django.utils.cache import cache_page

class CacheMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.method == 'GET':
            response = cache_page(60 * 15)(self.get_response)(request)
        return response