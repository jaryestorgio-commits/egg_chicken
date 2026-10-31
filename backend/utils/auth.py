from functools import wraps
from flask_jwt_extended import get_jwt_identity, jwt_required
from extensions import db
from models.user import User
from utils.responses import error_response


def current_user():
    identity = get_jwt_identity()
    try:
        return db.session.get(User, int(identity))
    except (TypeError, ValueError):
        return None


def roles_required(*roles):
    def decorator(view):
        @wraps(view)
        @jwt_required()
        def wrapped(*args, **kwargs):
            user = current_user()
            if user is None:
                return error_response("User account not found", status=401)
            if user.role not in roles:
                return error_response("Admin access required", status=403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def login_required(view):
    @wraps(view)
    @jwt_required()
    def wrapped(*args, **kwargs):
        user = current_user()
        if user is None:
            return error_response("User account not found", status=401)
        return view(*args, **kwargs)
    return wrapped