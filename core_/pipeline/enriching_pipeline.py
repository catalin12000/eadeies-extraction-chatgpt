from __future__ import annotations

from typing import Dict
from core_.base.datatypes import OpenAIConfig, FeaturePrediction
from core_.base.openai_config import OPENAI_CONFIG
from core_.features.permit_features import PermitFeatures
from core_.pipeline.pipe import Pipe


class EnrichingPipeline:
    def __init__(self, openai_config: OpenAIConfig = OPENAI_CONFIG):
        self.openai_config = openai_config
        self.pipes = [Pipe(f, openai_config) for f in PermitFeatures.ALL]

    def extract_features(self, text: str) -> Dict[str, FeaturePrediction]:
        return {pipe.feature.name: pipe.predict_feature(text) for pipe in self.pipes}
