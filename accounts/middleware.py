"""
Accounts middleware.

NoCacheMiddleware — adds Cache-Control: no-store to every response so that
authenticated pages are never served from browser or proxy caches.
"""
from django.utils.cache import patch_response_headers


class NoCacheMiddleware:
    """Set Cache-Control: no-store on all responses."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response["Cache-Control"] = "no-store"
        return response
