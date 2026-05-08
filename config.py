import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Base configuration"""
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-change-in-production")
    DEBUG = False
    TESTING = False

class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    GRAPHDB_ENDPOINT = os.getenv(
        "GRAPHDB_ENDPOINT",
        "http://localhost:7200/repositories/meadiverto"
    )

class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    GRAPHDB_ENDPOINT = os.getenv("GRAPHDB_ENDPOINT")

class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    GRAPHDB_ENDPOINT = os.getenv(
        "GRAPHDB_ENDPOINT",
        "http://localhost:7200/repositories/meadiverto"
    )

config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig
}
