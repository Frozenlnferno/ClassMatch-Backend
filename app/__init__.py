from flask import Flask
from .extensions import cors, get_supabase_client
from .config import Config
from dotenv import load_dotenv

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    cors.init_app(
        app, 
        origins=[app.config["FRONTEND_ORIGIN"]], 
        supports_credentials=True)

    app.supabase = get_supabase_client()

    # Register blueprints
    from .routes import main
    app.register_blueprint(main.bp) # No url_prefix means it's the root

    # Import models
    from . import models

    return app
