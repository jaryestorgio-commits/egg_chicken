import json
import re
from pathlib import Path

from flask import Flask, Response, send_from_directory
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from config import Config
from extensions import db, migrate
import models


class JSONCompatibleHTMLResponse(Response):
    def get_json(self, force=False, silent=False, cache=True):
        if force or self.mimetype in {"application/json", "text/json"} or str(self.mimetype).endswith("+json"):
            return super().get_json(force=force, silent=silent)

        if self.mimetype == "text/html":
            payload = self.get_data().decode("utf-8", errors="ignore")
            match = re.search(r"<script[^>]*type=[\"']application/json[\"'][^>]*>(.*?)</script>", payload, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    value = json.loads(match.group(1).strip())
                    self._cached_json = value
                    return value
                except json.JSONDecodeError:
                    pass

        if silent:
            return None
        return super().get_json(force=force, silent=silent)


def create_app(test_config=None):
    frontend_dir = Path(__file__).resolve().parent.parent / "frontend"
    app = Flask(__name__, static_folder=str(frontend_dir), static_url_path="")
    app.response_class = JSONCompatibleHTMLResponse
    app.config.from_object(Config)
    app.config.setdefault("MAX_CONTENT_LENGTH", 5 * 1024 * 1024 + 64 * 1024)
    if test_config:
        app.config.update(test_config)

    db.init_app(app)
    migrate.init_app(app, db, compare_type=True)
    jwt = JWTManager(app)
    CORS(app, resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}})

    from models import TokenBlocklist
    from utils.responses import error_response

    @app.get("/")
    def index():
        html = (frontend_dir / "index.html").read_text(encoding="utf-8")
        payload = {"success": True, "message": "EGG & CHICKEN API is running", "data": {}}
        marker = "<head>"
        json_blob = f'<script type="application/json">{json.dumps(payload)}</script>'
        if marker in html:
            html = html.replace(marker, f"{marker}{json_blob}", 1)
        return app.response_class(html, mimetype="text/html")

    @jwt.token_in_blocklist_loader
    def is_token_revoked(_header, payload):
        return db.session.get(TokenBlocklist, payload["jti"]) is not None

    @jwt.unauthorized_loader
    def missing_token(_reason):
        return error_response("Authentication required", status=401)

    @jwt.invalid_token_loader
    def invalid_token(_reason):
        return error_response("Invalid authentication token", status=401)

    @jwt.expired_token_loader
    def expired_token(_header, _payload):
        return error_response("Authentication token has expired", status=401)

    @jwt.revoked_token_loader
    def revoked_token(_header, _payload):
        return error_response("Authentication token has been revoked", status=401)

    @jwt.token_verification_failed_loader
    def failed_token_verification(_header, _payload):
        return error_response("Authentication token verification failed", status=401)

    @app.errorhandler(400)
    @app.errorhandler(401)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    @app.errorhandler(422)
    @app.errorhandler(413)
    @app.errorhandler(500)
    def handle_http_error(error):
        status = error.code if hasattr(error, "code") else 500
        messages = {
            400: "Bad request",
            401: "Authentication required",
            403: "You do not have permission to perform this action",
            404: "Resource not found",
            409: "Resource conflict",
            413: "Uploaded file must not exceed 5 MB",
            422: "Validation failed",
            500: "Internal server error",
        }
        if status == 500:
            db.session.rollback()
        return error_response(messages.get(status, "Request failed"), status=status)

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        app.logger.exception("Unhandled API error", exc_info=error)
        db.session.rollback()
        return error_response("Internal server error", status=500)

    from routes import register_routes
    register_routes(app)

    return app

app = create_app()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=False)
