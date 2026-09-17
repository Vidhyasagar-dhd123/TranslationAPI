"""
Standard API Response and Exception utilities.
"""
from django.http import JsonResponse


def api_response(data=None, message="Success", status=200, **kwargs):
    payload = {
        "success": True,
        "message": message,
        "data": data if data is not None else {},
    }
    payload.update(kwargs)
    return JsonResponse(payload, status=status)


def api_error(message="An error occurred", error_code="ERROR", status=400, details=None):
    payload = {
        "success": False,
        "error": {
            "code": error_code,
            "message": message,
            "details": details or {},
        }
    }
    return JsonResponse(payload, status=status)
