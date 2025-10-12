"""
ASGI config for gce_project project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gce_project.settings')

try:
    from channels.routing import ProtocolTypeRouter, URLRouter
    from channels.security.websocket import AllowedHostsOriginValidator

    # Initialize Django first, then import routing that touches Django apps
    django_asgi_app = get_asgi_application()
    import main.routing

    application = ProtocolTypeRouter({
        'http': django_asgi_app,
        'websocket': AllowedHostsOriginValidator(URLRouter(main.routing.websocket_urlpatterns)),
    })
except Exception:
    # Fallback: HTTP only
    application = get_asgi_application()
