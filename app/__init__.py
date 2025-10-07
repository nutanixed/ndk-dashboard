"""
NDK Dashboard - Flask Application Factory
"""
from flask import Flask
from datetime import timedelta
from config import Config


def create_app(config_class=Config):
    """Application factory pattern"""
    app = Flask(__name__, 
                template_folder='../templates',
                static_folder='../static')
    app.config.from_object(config_class)
    
    # Set session configuration
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=config_class.SESSION_TIMEOUT_HOURS)
    
    # Initialize extensions
    from app.extensions import init_extensions
    init_extensions(app)
    
    # Register blueprints
    from app.routes import (
        main_bp, auth_bp, applications_bp, snapshots_bp,
        storage_bp, protectionplans_bp, deployment_bp
    )
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(applications_bp, url_prefix='/api')
    app.register_blueprint(snapshots_bp, url_prefix='/api')
    app.register_blueprint(storage_bp, url_prefix='/api')
    app.register_blueprint(protectionplans_bp, url_prefix='/api')
    app.register_blueprint(deployment_bp, url_prefix='/api')
    
    return app