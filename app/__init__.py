"""Flask application factory"""

from flask import Flask
from config import config
from app.services.graphdb_service import GraphDBService

graphdb_service = None

def create_app(config_name="development"):
    """
    Create and configure Flask application
    
    Args:
        config_name: Configuration environment (development, production, testing)
        
    Returns:
        Flask: Configured Flask application
    """
    global graphdb_service
    
    app = Flask(__name__)
    
    # Load configuration
    app_config = config.get(config_name, config["default"])
    app.config.from_object(app_config)
    
    # Initialize GraphDB service
    graphdb_service = GraphDBService(app.config["GRAPHDB_ENDPOINT"])
    
    # Register blueprints
    from app.routes import main_bp, entity_bp
    
    app.register_blueprint(main_bp.bp)
    app.register_blueprint(entity_bp.bp)
    
    return app

def get_graphdb_service():
    """Get the GraphDB service instance"""
    global graphdb_service
    if graphdb_service is None:
        raise RuntimeError("GraphDB service not initialized. Call create_app() first.")
    return graphdb_service
