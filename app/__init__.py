from dotenv import load_dotenv
from flask import Flask
from urllib.parse import urlparse

load_dotenv()

from .routes.schedules import controller as schedules_controller
from .routes.groups import controller as groups_controller
from .routes.users import controller as users_controller

from .extensions import cors, init_db_pool
from .config import Config


def _build_cors_origins(frontend_origin):
    origins = set()
    if frontend_origin:
        origins.add(frontend_origin)

        parsed = urlparse(frontend_origin)
        if parsed.hostname in {"localhost", "127.0.0.1"} and parsed.port:
            alt_host = "127.0.0.1" if parsed.hostname == "localhost" else "localhost"
            alt_origin = parsed._replace(netloc=f"{alt_host}:{parsed.port}").geturl()
            origins.add(alt_origin)

    return sorted(origins)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Disable strict trailing slash to prevent redirects
    app.url_map.strict_slashes = False

    # Initialize extensions
    cors.init_app(
        app, 
        origins=_build_cors_origins(app.config["FRONTEND_ORIGIN"]),
        supports_credentials=True,
        methods=["GET","POST","OPTIONS","PUT","DELETE","PATCH"],
        allow_headers=["Authorization", "Content-Type"]
    )
    
    # Initialize database pool
    init_db_pool()

    # Register blueprints
    from .routes import main
    app.register_blueprint(main.bp) # No url_prefix means it's the root
    app.register_blueprint(schedules_controller.bp, url_prefix="/api/schedules")
    app.register_blueprint(groups_controller.bp, url_prefix="/api/groups")
    app.register_blueprint(users_controller.bp, url_prefix="/api/users")

    # Import models
    from . import models

    return app
