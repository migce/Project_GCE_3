from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r"^ws/mt5/open_positions/?$", consumers.Mt5OpenPositionsConsumer.as_asgi()),
]

