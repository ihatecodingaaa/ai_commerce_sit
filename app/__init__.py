import os

from flask import Flask

from app.config import config


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    os.makedirs(config.LOG_DIR, exist_ok=True)
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)

    from app.routes.auth_routes import bp as auth_bp
    from app.routes.pages import bp as pages_bp
    from app.routes.api_products import bp as products_bp
    from app.routes.api_orders import bp as orders_bp
    from app.routes.api_support import bp as support_bp
    from app.routes.api_chat import bp as chat_bp
    from app.routes.api_images import bp as images_bp
    from app.routes.health import bp as health_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(health_bp)

    from app.services.rotation import start_rotation_scheduler

    start_rotation_scheduler(config.TOKEN_ROTATION_INTERVAL_SECONDS)

    return app
