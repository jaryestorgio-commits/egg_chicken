from flask import Blueprint, request
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import Address, User
from utils.auth import current_user, login_required
from utils.responses import error_response, success_response
from utils.validators import request_data, required_string, valid_email


users_bp = Blueprint("users", __name__)
ADDRESS_FIELDS = ("full_name", "phone", "address_line", "city", "province", "postal_code")


@users_bp.get("/me")
@login_required
def get_profile():
    return success_response({"user": current_user().to_dict()})


@users_bp.put("/me")
@users_bp.patch("/me")
@login_required
def update_profile():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    user = current_user()
    errors = {}
    if "name" in data:
        user.name, error = required_string(data, "name", max_length=120)
        if error:
            errors["name"] = error
    if "email" in data:
        email, error = required_string(data, "email", max_length=120)
        if error or not valid_email(email):
            errors["email"] = error or "Enter a valid email address"
        else:
            email = email.lower()
            existing = User.query.filter(User.email == email, User.id != user.id).first()
            if existing:
                return error_response("Email already registered", status=409)
            user.email = email
    if errors:
        db.session.rollback()
        return error_response("Validation failed", errors, 400)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response("Email already exists", status=409)
    return success_response({"user": user.to_dict()}, "Profile updated")


@users_bp.put("/me/password")
@login_required
def update_password():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    current_password, current_error = required_string(data, "current_password", max_length=256)
    new_password, new_error = required_string(data, "new_password", max_length=256)
    errors = {}
    if current_error:
        errors["current_password"] = current_error
    if new_error:
        errors["new_password"] = new_error
    elif len(new_password) < 8:
        errors["new_password"] = "Password must be at least 8 characters"
    if errors:
        return error_response("Validation failed", errors, 400)

    user = current_user()
    if not user.check_password(current_password):
        return error_response("Current password is incorrect", status=401)
    user.set_password(new_password)
    db.session.commit()
    return success_response({}, "Password updated")


@users_bp.get("/me/addresses")
@login_required
def list_addresses():
    addresses = Address.query.filter_by(user_id=current_user().id).order_by(Address.is_default.desc(), Address.id).all()
    return success_response({"addresses": [address.to_dict() for address in addresses]})


@users_bp.post("/me/addresses")
@login_required
def create_address():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    values = {}
    errors = {}
    for field in ADDRESS_FIELDS:
        value, error = required_string(data, field, max_length=300)
        if error:
            errors[field] = error
        else:
            values[field] = value
    if errors:
        return error_response("Validation failed", errors, 422)
    user_id = current_user().id
    is_default = bool(data.get("is_default", False))
    if is_default:
        Address.query.filter_by(user_id=user_id, is_default=True).update({"is_default": False})
    address = Address(user_id=user_id, is_default=is_default, **values)
    db.session.add(address)
    db.session.commit()
    return success_response({"address": address.to_dict()}, "Address created", 201)


@users_bp.patch("/me/addresses/<int:address_id>")
@login_required
def update_address(address_id):
    address = Address.query.filter_by(id=address_id, user_id=current_user().id).first_or_404()
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    errors = {}
    for field in ADDRESS_FIELDS:
        if field in data:
            value, error = required_string(data, field, max_length=300)
            if error:
                errors[field] = error
            else:
                setattr(address, field, value)
    if "is_default" in data:
        if not isinstance(data["is_default"], bool):
            errors["is_default"] = "is_default must be a boolean"
        elif data["is_default"]:
            Address.query.filter(Address.user_id == address.user_id, Address.id != address.id).update({"is_default": False})
            address.is_default = True
        else:
            address.is_default = False
    if errors:
        db.session.rollback()
        return error_response("Validation failed", errors, 422)
    db.session.commit()
    return success_response({"address": address.to_dict()}, "Address updated")


@users_bp.delete("/me/addresses/<int:address_id>")
@login_required
def delete_address(address_id):
    address = Address.query.filter_by(id=address_id, user_id=current_user().id).first_or_404()
    db.session.delete(address)
    db.session.commit()
    return success_response({}, "Address deleted")