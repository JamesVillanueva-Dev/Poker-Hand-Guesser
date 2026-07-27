from __future__ import annotations

from database.repository import SQLiteRepository
from engine.likelihood import PolicyLikelihood
from engine.range_engine import RangeEstimator

repository = SQLiteRepository()
range_estimator = RangeEstimator(likelihood_model=PolicyLikelihood())


def get_repository() -> SQLiteRepository:
    return repository


def get_range_estimator() -> RangeEstimator:
    return range_estimator
