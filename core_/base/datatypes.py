"""Core datatypes used across the permit extraction pipeline.

Minimal implementations to allow a demonstration extraction script.
"""
from __future__ import annotations

from typing import Optional, List, Dict, Any, Union, Callable
from pydantic import BaseModel
import os


class FeatureConfig(BaseModel):
    name: str
    column_name: str
    prompt: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    value_type: type = str
    allowed_values: Optional[List[Any]] = None
    patterns: List[str] = []
    is_binary: bool = False
    european_format: bool = False
    fixed_matches: Optional[Dict[str, int]] = None


class OpenAIResponse(BaseModel):
    text: str
    cost: float
    logprob: Optional[float] = None


class FeaturePrediction(BaseModel):
    feature_name: str
    predicted_value: Union[int, float, str, None]
    logprob: Optional[float] = None
    cost: float = 0.0
    method: str = "strict_regex"


class OpenAIConfig(BaseModel):
    API_KEY: str = os.getenv("API_KEY", "")
    MODEL: str = "gpt-4.1-mini-2025-04-14"
    TEMPERATURE: int = 0
    MAX_TOKENS: int = 50
    COST_PER_TOKEN: float = 0.0000025


class Feature(BaseModel):
    name: str
    column_name: str
    prompt: str
    strict_prediction: Callable[[str], FeaturePrediction]
    validate_func: Callable[[Any], Any]
