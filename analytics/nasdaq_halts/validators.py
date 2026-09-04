from __future__ import annotations

from datetime import date

from .models import AnalysisRequest


def validate_request(request: AnalysisRequest) -> AnalysisRequest:
    request = request.normalized()

    if not isinstance(request.observation_date, date):
        raise ValueError("observation_date must be a date")

    return request
