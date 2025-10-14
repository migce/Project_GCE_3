"""
ASGI config for gce_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from django.conf import settings

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gce_project.settings')

try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator

    # Initialize Django first, then import routing that touches Django apps
    django_asgi_app = get_asgi_application()
    # Serve static files via ASGI in DEBUG so Daphne can return CSS/JS
    try:
        if getattr(settings, 'DEBUG', False):
            from django.contrib.staticfiles.handlers import ASGIStaticFilesHandler
            django_asgi_app = ASGIStaticFilesHandler(django_asgi_app)
    except Exception:
        pass
    import main.routing

    application = ProtocolTypeRouter({
        'http': django_asgi_app,
        'websocket': AllowedHostsOriginValidator(URLRouter(main.routing.websocket_urlpatterns)),
    })
except Exception:
    # Fallback: HTTP only
    application = get_asgi_application()
