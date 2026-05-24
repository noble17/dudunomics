"""dash-auth Basic Auth 설정."""
import os

from dash import Dash


def apply_auth(app: Dash):
    username = os.getenv("BASIC_AUTH_USERNAME")
    password = os.getenv("BASIC_AUTH_PASSWORD")
    if username and password:
        from dash_auth import BasicAuth
        BasicAuth(app, {username: password})
