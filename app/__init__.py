from flask import Flask

from .routes.schedules import controller as schedule_controller
from .extensions import cors, init_db_pool
from .config import Config
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Disable strict trailing slash to prevent redirects
    app.url_map.strict_slashes = False

    # Initialize extensions
    cors.init_app(
        app, 
        origins=[Config.FRONTEND_ORIGIN, app.config["FRONTEND_ORIGIN"]], 
        supports_credentials=True,
        methods=["GET","POST","OPTIONS","PUT","DELETE"],
        allow_headers=["Authorization", "Content-Type"]
    )
    
    # Initialize database pool
    init_db_pool()

    # Register blueprints
    from .routes import main
    app.register_blueprint(main.bp) # No url_prefix means it's the root
    app.register_blueprint(schedule_controller.bp, url_prefix="/api/schedule/")

    # Import models
    from . import models

    return app
