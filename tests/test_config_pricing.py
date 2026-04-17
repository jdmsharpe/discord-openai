"""Tests for the YAML-backed pricing loader."""

import importlib
import sys
import textwrap
from pathlib import Path


def _reload_pricing():
    for mod_name in ("discord_openai.config.pricing",):
        sys.modules.pop(mod_name, None)
    return importlib.import_module("discord_openai.config.pricing")


class TestPricingLoader:
    def test_bundled_yaml_loads_model_pricing(self):
        pricing = _reload_pricing()
        assert pricing.MODEL_PRICING["gpt-5"] == (1.25, 10.0)
        assert pricing.MODEL_PRICING["gpt-4o"] == (2.5, 10.0)

    def test_bundled_yaml_loads_tool_pricing(self):
        pricing = _reload_pricing()
        assert pricing.TOOL_CALL_PRICING["web_search"] == 0.01
        assert pricing.TOOL_CALL_PRICING["code_interpreter"] == 0.03

    def test_bundled_yaml_flattens_image_pricing(self):
        pricing = _reload_pricing()
        assert pricing.IMAGE_PRICING[("gpt-image-1.5", "low", "1024x1024")] == 0.009
        assert pricing.IMAGE_PRICING[("gpt-image-1", "high", "1536x1024")] == 0.25

    def test_bundled_yaml_loads_image_defaults(self):
        pricing = _reload_pricing()
        assert pricing.IMAGE_PRICING_DEFAULTS["gpt-image-1.5"] == 0.034

    def test_bundled_yaml_loads_tts_stt_video(self):
        pricing = _reload_pricing()
        assert pricing.TTS_PRICING_PER_CHAR["tts-1"] == 0.000015
        assert pricing.STT_PRICING_PER_MINUTE["whisper-1"] == 0.006
        assert pricing.VIDEO_PRICING_PER_SECOND["sora-2"] == 0.10
        assert pricing.VIDEO_PRICING_PER_SECOND["sora-2-pro"] == 0.20

    def test_fallback_constants_loaded(self):
        pricing = _reload_pricing()
        assert pricing.UNKNOWN_CHAT_MODEL_PRICING == (2.5, 10.0)
        assert pricing.UNKNOWN_IMAGE_MODEL_PRICING == 0.034
        assert pricing.UNKNOWN_TTS_MODEL_PRICING == 0.000015
        assert pricing.UNKNOWN_STT_MODEL_PRICING == 0.006
        assert pricing.UNKNOWN_VIDEO_MODEL_PRICING == 0.10

    def test_env_var_override_path(self, monkeypatch, tmp_path: Path):
        custom_yaml = tmp_path / "custom-pricing.yaml"
        custom_yaml.write_text(
            textwrap.dedent(
                """
                models:
                  custom-model:
                    input_per_million: 1.5
                    output_per_million: 3.0
                tools:
                  custom_tool:
                    per_call: 0.007
                image_generation:
                  fake-image:
                    default_per_image: 0.99
                    by_quality_size:
                      high:
                        1024x1024: 1.23
                text_to_speech:
                  fake-tts:
                    per_character: 0.0001
                speech_to_text:
                  fake-stt:
                    per_minute: 0.02
                video_generation:
                  fake-video:
                    per_second: 0.5
                fallbacks:
                  unknown_chat_model: { input_per_million: 42.0, output_per_million: 100.0 }
                  unknown_image_model: { per_image: 0.5 }
                  unknown_tts_model: { per_character: 0.0005 }
                  unknown_stt_model: { per_minute: 0.1 }
                  unknown_video_model: { per_second: 1.0 }
                """
            ).strip()
        )
        monkeypatch.setenv("OPENAI_PRICING_PATH", str(custom_yaml))

        pricing = _reload_pricing()

        assert pricing.MODEL_PRICING == {"custom-model": (1.5, 3.0)}
        assert pricing.TOOL_CALL_PRICING == {"custom_tool": 0.007}
        assert pricing.IMAGE_PRICING[("fake-image", "high", "1024x1024")] == 1.23
        assert pricing.IMAGE_PRICING_DEFAULTS == {"fake-image": 0.99}
        assert pricing.UNKNOWN_CHAT_MODEL_PRICING == (42.0, 100.0)
        assert pricing.UNKNOWN_VIDEO_MODEL_PRICING == 1.0
