from flask import Blueprint, request
from sqlalchemy.exc import IntegrityError
from extensions import db
from models import Category
from utils.auth import roles_required
from utils.responses import error_response, success_response
from utils.validators import request_data, required_string

categories_bp = Blueprint("categories", __name__)

@categories_bp.get("")
def get_categories():
    categories = Category.query.order_by(Category.name).all()
    return success_response({"categories": [category.to_dict() for category in categories]})


@categories_bp.get("/<int:category_id>")
def get_category(category_id):
    category = Category.query.get_or_404(category_id)
    return success_response({"category": category.to_dict()})

@categories_bp.post("")
@roles_required("admin")
def create_category():
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    name, error = required_string(data, "name", max_length=100)
    if error:
        return error_response("Validation failed", {"name": error}, 422)
    category = Category(name=name, description=data.get("description"))
    db.session.add(category)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response("A category with that name already exists", status=409)
    return success_response({"category": category.to_dict()}, "Category created", 201)


@categories_bp.patch("/<int:category_id>")
@roles_required("admin")
def update_category(category_id):
    category = Category.query.get_or_404(category_id)
    data = request_data(request)
    if data is None:
        return error_response("A JSON object is required", status=400)
    errors = {}
    if "name" in data:
        name, error = required_string(data, "name", max_length=100)
        if error:
            errors["name"] = error
        else:
            category.name = name
    if "description" in data:
        description = data["description"]
        if description is not None and not isinstance(description, str):
            errors["description"] = "description must be text"
        else:
            category.description = description
    if errors:
        db.session.rollback()
        return error_response("Validation failed", errors, 422)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        return error_response("A category with that name already exists", status=409)
    return success_response({"category": category.to_dict()}, "Category updated")


@categories_bp.delete("/<int:category_id>")
@roles_required("admin")
def delete_category(category_id):
    category = Category.query.get_or_404(category_id)
    db.session.delete(category)
    db.session.commit()
    return success_response({}, "Category deleted")
