from flask import jsonify
from pydantic import ValidationError


class ApiError(Exception):
    def __init__(self, message, status_code=400, code=None, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.code = code or "api_error"
        self.details = details


def error_payload(message, code="api_error", details=None):
    payload = {"error": message, "code": code}
    if details is not None:
        payload["details"] = details
    return payload


def error_response(message, status_code=400, code="api_error", details=None):
    return jsonify(error_payload(message, code, details)), status_code


def _pydantic_details(exc):
    return [
        {
            "field": ".".join(str(part) for part in err.get("loc", [])),
            "message": err.get("msg"),
            "type": err.get("type"),
        }
        for err in exc.errors()
    ]


def register_error_handlers(app):
    from backend.providers import ProviderError

    @app.errorhandler(ApiError)
    def handle_api_error(exc):
        return error_response(exc.message, exc.status_code, exc.code, exc.details)

    @app.errorhandler(ValidationError)
    def handle_validation_error(exc):
        return error_response(
            "Validation failed",
            400,
            "validation_error",
            _pydantic_details(exc),
        )

    @app.errorhandler(ProviderError)
    def handle_provider_error(exc):
        return error_response(
            "Market-data provider request failed",
            502,
            "provider_error",
            exc.to_dict(),
        )

    @app.errorhandler(404)
    def handle_not_found(_exc):
        return error_response("Not found", 404, "not_found")

    @app.errorhandler(405)
    def handle_method_not_allowed(_exc):
        return error_response("Method not allowed", 405, "method_not_allowed")

    @app.errorhandler(500)
    def handle_internal_error(_exc):
        return error_response("Internal server error", 500, "internal_error")
