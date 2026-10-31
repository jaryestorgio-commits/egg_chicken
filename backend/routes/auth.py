from flask import Blueprint, request
from flask_jwt_extended import (
    create_access_token,
    jwt_required,
    get_jwt,
)
from extensions import db
from models import TokenBlocklist, User
from utils.auth import current_user
from utils.responses import success_response, error_response
from utils.validators import request_data, required_string, valid_email

auth_bp = Blueprint("auth", __name__)

@auth_bp.post("/register")
def register():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    name, error = required_string(data, "name", max_length=120)
    if error:
        return error_response("Validation failed", {"name": error}, 400)
    email, error = required_string(data, "email", max_length=120)
    if error or not valid_email(email):
        return error_response("Validation failed", {"email": error or "Enter a valid email address"}, 400)
    email = email.lower()
    password, error = required_string(data, "password", max_length=256)
    if error or len(password) < 8:
        return error_response("Validation failed", {"password": error or "Password must be at least 8 characters"}, 400)
    if User.query.filter_by(email=email).first():
        return error_response("Email already registered", status=409)

    user = User(name=name, email=email)
    user.set_password(password)

    db.session.add(user)
    db.session.commit()

    token = create_access_token(identity=str(user.id))
    return success_response({"user": user.to_dict(), "access_token": token}, "Registration successful", 201)

@auth_bp.post("/login")
def login():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    email = data.get("email")
    password = data.get("password")
    if not isinstance(email, str) or not isinstance(password, str):
        return error_response("Email and password are required", status=400)
    user = User.query.filter_by(email=email.strip().lower()).first()

    if not user or not user.check_password(password):
        return error_response("Invalid email or password", status=401)

    token = create_access_token(identity=str(user.id))

    return success_response({"access_token": token, "user": user.to_dict()}, "Login successful")

@auth_bp.get("/me")
@jwt_required()
def me():
    user = current_user()
    if user is None:
        return error_response("User not found", status=404)
    return success_response({"user": user.to_dict()})


@auth_bp.post("/logout")
@jwt_required()
def logout():
    db.session.add(TokenBlocklist(jti=get_jwt()["jti"]))
    db.session.commit()
    return success_response({}, "Logout successful")
