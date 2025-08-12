from __future__ import annotations

from core_.base.datatypes import Feature, FeaturePrediction, OpenAIConfig, OpenAIResponse
from typing import Any
import logging

try:
    import openai  # type: ignore
except ImportError:
    openai = None  # type: ignore

logger = logging.getLogger(__name__)


class Pipe:
    def __init__(self, feature: Feature, openai_config: OpenAIConfig):
        self.feature = feature
        self.openai_config = openai_config

    def _predict_via_llm(self, text: str) -> OpenAIResponse:
        if openai is None or not self.openai_config.API_KEY:
            return OpenAIResponse(text="a", cost=0.0, logprob=None)
        openai.api_key = self.openai_config.API_KEY
        try:
            resp = openai.ChatCompletion.create(
                model=self.openai_config.MODEL,
                messages=[
                    {"role": "system", "content": self.feature.prompt},
                    {"role": "user", "content": text[:15000]},
                ],
                temperature=self.openai_config.TEMPERATURE,
                max_tokens=self.openai_config.MAX_TOKENS,
            )
            content = resp.choices[0].message["content"].strip()
            total_tokens = resp.usage.get("total_tokens", 0) if hasattr(resp, "usage") else 0
            cost = total_tokens * self.openai_config.COST_PER_TOKEN
            return OpenAIResponse(text=content, cost=cost, logprob=None)
        except Exception as e:
            logger.warning("OpenAI failure (%s): %s", self.feature.name, e)
            return OpenAIResponse(text="a", cost=0.0, logprob=None)

    def predict_feature(self, text: str) -> FeaturePrediction:
        strict_pred = self.feature.strict_prediction(text)
        if strict_pred.predicted_value is not None:
            return strict_pred
        response = self._predict_via_llm(text)
        validated = self.feature.validate_func(response.text)
        return FeaturePrediction(
            feature_name=self.feature.name,
            predicted_value=validated if validated is not None else response.text,
            method="openai",
            cost=response.cost,
            logprob=response.logprob,
        )
