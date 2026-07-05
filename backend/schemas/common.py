from flask import request
from pydantic import BaseModel, ConfigDict, ValidationError

from backend.errors import ApiError


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


def _validation_details(exc):
    return [
        {
            "field": ".".join(str(part) for part in err.get("loc", [])),
            "message": err.get("msg"),
            "type": err.get("type"),
        }
        for err in exc.errors()
    ]


def parse_json(model_cls):
    data = request.get_json(silent=True)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ApiError("Request body must be a JSON object", 400, "validation_error")
    try:
        return model_cls.model_validate(data)
    except ValidationError as exc:
        raise ApiError(
            "Validation failed",
            400,
            "validation_error",
            _validation_details(exc),
        )


def parse_query(model_cls):
    try:
        return model_cls.model_validate(request.args.to_dict(flat=True))
    except ValidationError as exc:
        raise ApiError(
            "Validation failed",
            400,
            "validation_error",
            _validation_details(exc),
        )
