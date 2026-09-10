import os

from flask import Flask, render_template

from app.config import config


def create_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = config.SECRET_KEY

    from app.avatars import PRESET_AVATARS, avatar_by_key, avatar_css_class

    app.jinja_env.globals["PRESET_AVATARS"] = PRESET_AVATARS
    app.jinja_env.globals["avatar_emoji"] = lambda key: avatar_by_key(key)["emoji"]
    app.jinja_env.globals["avatar_class"] = avatar_css_class

    @app.errorhandler(403)
    def forbidden(_e):
        from app.auth import current_user
        return render_template("error.html", user=current_user(), code=403, message="You don't have access to this page."), 403

    @app.errorhandler(404)
    def not_found(_e):
        from app.auth import current_user
        return render_template("error.html", user=current_user(), code=404, message="That page doesn't exist."), 404

    os.makedirs(config.LOG_DIR, exist_ok=True)
    os.makedirs(config.UPLOAD_DIR, exist_ok=True)
    os.makedirs(config.PRODUCT_PHOTO_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(config.DATABASE_PATH), exist_ok=True)

    from app.routes.auth_routes import bp as auth_bp
    from app.routes.pages import bp as pages_bp
    from app.routes.admin import bp as admin_bp
    from app.routes.api_products import bp as products_bp
    from app.routes.api_orders import bp as orders_bp
    from app.routes.api_support import bp as support_bp
    from app.routes.api_chat import bp as chat_bp
    from app.routes.api_images import bp as images_bp
    from app.routes.api_admin import bp as api_admin_bp
    from app.routes.api_account import bp as api_account_bp
    from app.routes.health import bp as health_bp

    app.register_blueprint(pages_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(products_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(support_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(images_bp)
    app.register_blueprint(api_admin_bp)
    app.register_blueprint(api_account_bp)
    app.register_blueprint(health_bp)

    from app.services.rotation import start_rotation_scheduler

    start_rotation_scheduler(config.TOKEN_ROTATION_INTERVAL_SECONDS)

    return app
