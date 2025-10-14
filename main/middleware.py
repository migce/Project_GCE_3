from django.conf import settings
from django.shortcuts import redirect
from django.urls import reverse
import re


class LoginRequiredMiddleware:
    """Redirect anonymous users to the login page for all non-static paths.

    Whitelist minimal paths so login and static assets remain accessible.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Precompile simple allowlist patterns
        login_path = '/auth/login/'
        logout_path = '/auth/logout/'
        self.allow = [
            re.compile(r'^/static/'),
            re.compile(r'^/favicon\.ico$'),
            re.compile(r'^/auth/login/?$'),
            re.compile(r'^/auth/logout/?$'),
            # Allow Django admin login and its static assets
            re.compile(r'^/admin/login/?$'),
            re.compile(r'^/admin/logout/?$'),
            re.compile(r'^/admin/js/'),
            re.compile(r'^/admin/css/'),
            re.compile(r'^/admin/img/'),
        ]

    def __call__(self, request):
        path = request.path or '/'
        if request.user.is_authenticated:
            return self.get_response(request)

        # Allow whitelist paths without auth
        for pat in self.allow:
            if pat.match(path):
                return self.get_response(request)

        # Redirect to LOGIN_URL with ?next=
        login_url = settings.LOGIN_URL
        try:
            login_url = reverse(login_url)
        except Exception:
            # If LOGIN_URL is already a path or namespaced incorrectly
            login_url = settings.LOGIN_URL if isinstance(settings.LOGIN_URL, str) else '/auth/login/'

        return redirect(f"{login_url}?next={path}")

