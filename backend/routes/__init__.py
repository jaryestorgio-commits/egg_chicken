
from .health import health_bp
from .auth import auth_bp
from .products import products_bp
from .categories import categories_bp
from .cart import cart_bp
from .orders import orders_bp
from .admin import admin_bp
from .admin_activity import admin_activity_bp
from .inventory import inventory_bp
from .payments import payments_bp
from .chat import chat_bp, admin_chat_bp
from .users import users_bp


def register_routes(app):
    app.register_blueprint(health_bp, url_prefix="/api/v1")
    app.register_blueprint(auth_bp, url_prefix="/api/v1/auth")
    app.register_blueprint(products_bp, url_prefix="/api/v1/products")
    app.register_blueprint(categories_bp, url_prefix="/api/v1/categories")
    app.register_blueprint(cart_bp, url_prefix="/api/v1/cart")
    app.register_blueprint(orders_bp, url_prefix="/api/v1/orders")

    # Admin module
    app.register_blueprint(admin_bp, url_prefix="/api/v1/admin")
    app.register_blueprint(
        admin_activity_bp, url_prefix="/api/v1/admin"
    )
    app.register_blueprint(
        admin_chat_bp, url_prefix="/api/v1/admin"
    )

    # Other API modules
    app.register_blueprint(inventory_bp, url_prefix="/api/v1/inventory")
    app.register_blueprint(payments_bp, url_prefix="/api/v1/payments")
    app.register_blueprint(chat_bp, url_prefix="/api/v1/chat")
    app.register_blueprint(users_bp, url_prefix="/api/v1/users")
