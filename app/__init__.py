from dotenv import load_dotenv
from flask import Flask, g, jsonify, request
from time import perf_counter
from urllib.parse import urlparse
from uuid import uuid4
from werkzeug.exceptions import HTTPException

load_dotenv()

from .routes.schedules import schedules_controller
from .routes.groups import groups_controller
from .routes.users import users_controller

from .extensions import cors, init_db_pool
from .config import Config
from .utils.logger import configure_logging, get_logger


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
    configure_logging()
    app = Flask(__name__)
    app.config.from_object(Config)
    logger = get_logger(__name__)
    
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

    @app.before_request
    def _before_request():
        g.request_id = str(uuid4())
        g.request_start_time = perf_counter()

    @app.after_request
    def _after_request(response):
        start = getattr(g, "request_start_time", None)
        response_time_ms = 0.0
        if start is not None:
            response_time_ms = round((perf_counter() - start) * 1000, 2)

        logger.info(
            "HTTP request completed",
            extra={
                "status_code": response.status_code,
                "response_time_ms": response_time_ms,
            },
        )
        response.headers["X-Request-ID"] = getattr(g, "request_id", "-")
        return response

    @app.errorhandler(Exception)
    def _handle_exception(err):
        if isinstance(err, HTTPException):
            logger.warning(
                "HTTP exception",
                extra={
                    "status_code": err.code,
                    "error": err.description,
                },
            )
            return err

        logger.exception(
            "Unhandled exception",
            extra={
                "error": str(err),
            },
        )
        return jsonify({"error": "Internal server error"}), 500

    # Register blueprints
    from .routes import main
    app.register_blueprint(main.bp) # No url_prefix means it's the root
    app.register_blueprint(schedules_controller.bp, url_prefix="/api/schedules")
    app.register_blueprint(groups_controller.bp, url_prefix="/api/groups")
    app.register_blueprint(users_controller.bp, url_prefix="/api/users")

    # Import models
    from . import models

    return app
