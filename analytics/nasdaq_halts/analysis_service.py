from __future__ import annotations

from typing import Iterable

from .historical_dataset import build_historical_dataset
from .metric_calculator import calculate_metrics
from .models import AnalysisRequest, AnalysisResult
from .validators import validate_request


class AnalysisService:
    """Application-facing orchestration boundary for Nasdaq HALT analysis."""

    def __init__(self, core_source=None) -> None:
        self.core_source = core_source

    def analyze(
        self,
        request: AnalysisRequest,
        *,
        episodes: Iterable[dict] | None = None,
    ) -> AnalysisResult:
        req = validate_request(request)

        if episodes is None:
            if self.core_source is None:
                raise RuntimeError(
                    "No CORE source configured. Supply episodes or a core_source."
                )
            episodes = self.core_source.fetch_core_episodes(
                ticker=req.ticker,
                start_date=None,
                end_date=req.observation_date,
                reason_codes=req.reason_codes,
            )

        dataset = build_historical_dataset(req, episodes)

        return calculate_metrics(
            dataset,
            observation_date=req.observation_date,
            reason_codes=req.reason_codes,
        )
