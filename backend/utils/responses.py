from flask import jsonify


def success_response(data=None, message="Operation successful", status=200):
    return jsonify({"success": True, "message": message, "data": data if data is not None else {}}), status


def error_response(message, errors=None, status=400):
    return jsonify({"success": False, "message": message, "errors": errors if errors is not None else {}}), status