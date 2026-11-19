import threading

from django.http import HttpResponseForbidden
from django.contrib.auth import logout
from django.shortcuts import redirect

_state = threading.local()


def get_current_request():
    return getattr(_state, 'request', None)


def get_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR')


class CurrentUserMiddleware:
    """Hozirgi request'ni thread-local'da saqlaydi (audit_log uchun ip/user olish)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        _state.request = request
        try:
            return self.get_response(request)
        finally:
            _state.request = None


class BlockedUserMiddleware:
    """Bloklangan (is_active=False) hodimning sessiyasini darhol tugatadi."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if user is not None and user.is_authenticated and not user.is_active:
            logout(request)
            return redirect('accounts:login')
        return self.get_response(request)


class HtmxLoginRedirectMiddleware:
    """Sessiya tugagan bo'lsa HTMX so'rovi login sahifasini bo'lak ichiga joylab yubormasin,
    butun sahifa login'ga o'tsin (HX-Redirect)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.headers.get('HX-Request') == 'true' and response.status_code == 302:
            from django.http import HttpResponse
            from django.urls import reverse

            location = response.get('Location', '')
            if location.startswith(reverse('accounts:login')):
                redirect_response = HttpResponse(status=204)
                redirect_response['HX-Redirect'] = location
                return redirect_response
        return response
