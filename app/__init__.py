from flask import Flask
from .extensions import cors, get_supabase_client
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
        origins=["http://localhost:5173", app.config["FRONTEND_ORIGIN"]], 
        supports_credentials=True,
        methods=["GET","POST","OPTIONS","PUT","DELETE"],
        allow_headers=["Authorization", "Content-Type"]
    )

    app.supabase = get_supabase_client()

    # Register blueprints
    from .routes import main, schedule
    app.register_blueprint(main.bp) # No url_prefix means it's the root
    app.register_blueprint(schedule.bp, url_prefix="/api/schedule/")

    # Import models
    from . import models

    return app
