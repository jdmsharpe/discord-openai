"""Tests for the YAML-backed pricing loader."""

import importlib
import sys
import textwrap
from pathlib import Path

import pytest


def _reload_pricing():
    for mod_name in ("discord_openai.config.pricing",):
        sys.modules.pop(mod_name, None)
    return importlib.import_module("discord_openai.config.pricing")


class TestPricingLoader:
    def test_bundled_yaml_loads_model_pricing(self):
        pricing = _reload_pricing()
        assert pricing.MODEL_PRICING["gpt-5"] == (1.25, 10.0)
        assert pricing.MODEL_PRICING["gpt-4o"] == (2.5, 10.0)

    def test_gpt_5_6_family_rates_are_pinned(self):
        """Pin the default family's absolute rates.

        ``test_declared_cached_rates_match_published`` only checks the cached rate as a
        RATIO of input, so a row scaled uniformly stays a perfect 10% and passes — which
        is how terra and luna went unnoticed while overbilling 25% and 5x.
        """
        pricing = _reload_pricing()
        assert pricing.MODEL_PRICING["gpt-5.6-sol"] == (4.00, 20.00)  # promo through 2026-11-21
        assert pricing.MODEL_PRICING["gpt-5.6-terra"] == (2.00, 12.00)
        assert pricing.MODEL_PRICING["gpt-5.6-luna"] == (0.20, 1.20)
        assert pricing.CACHED_INPUT_PRICING["gpt-5.6-sol"] == 0.40
        assert pricing.CACHED_INPUT_PRICING["gpt-5.6-terra"] == 0.20
        assert pricing.CACHED_INPUT_PRICING["gpt-5.6-luna"] == 0.02

    def test_gpt_5_6_cache_write_rates_are_pinned(self):
        """Cache writes (1.25x input) are declared on the three gpt-5.6 rows and nowhere else."""
        pricing = _reload_pricing()
        assert pricing.CACHE_WRITE_PRICING == {
            "gpt-5.6-sol": 5.00,
            "gpt-5.6-terra": 2.50,
            "gpt-5.6-luna": 0.25,
        }

    def test_long_context_tiers_are_pinned(self):
        """Prompts over 272K input tokens bill 2x input / 1.5x output for the whole request.

        Published for the GPT-5.4 / 5.5 / 5.6 families only (pricing page tooltips
        "Short context <=272K" / "Long context >272K"; model pages: "for the full
        session"). Cache writes double with the input rate; the Pro tiers publish no
        cached rate at either tier.
        """
        pricing = _reload_pricing()
        assert set(pricing.LONG_CONTEXT_PRICING) == {
            "gpt-5.6-sol",
            "gpt-5.6-terra",
            "gpt-5.6-luna",
            "gpt-5.5",
            "gpt-5.5-pro",
            "gpt-5.4",
            "gpt-5.4-pro",
        }
        assert pricing.LONG_CONTEXT_PRICING["gpt-5.6-sol"] == {
            "threshold_tokens": 272001,
            "input_per_million": 8.00,
            "output_per_million": 30.00,
            "cached_input_per_million": 0.80,
            "cache_write_per_million": 10.00,
        }
        assert pricing.LONG_CONTEXT_PRICING["gpt-5.5"] == {
            "threshold_tokens": 272001,
            "input_per_million": 10.00,
            "output_per_million": 45.00,
            "cached_input_per_million": 1.00,
            "cache_write_per_million": None,
        }
        assert pricing.LONG_CONTEXT_PRICING["gpt-5.5-pro"]["cached_input_per_million"] is None
        for model, tier in pricing.LONG_CONTEXT_PRICING.items():
            base_input, base_output = pricing.MODEL_PRICING[model]
            assert tier["threshold_tokens"] == 272001, model
            assert tier["input_per_million"] == pytest.approx(2 * base_input), model
            assert tier["output_per_million"] == pytest.approx(1.5 * base_output), model
            if model in pricing.CACHED_INPUT_PRICING:
                cached = tier["cached_input_per_million"]
                assert cached == pytest.approx(2 * pricing.CACHED_INPUT_PRICING[model]), model
            if model in pricing.CACHE_WRITE_PRICING:
                assert tier["cache_write_per_million"] == pytest.approx(
                    2 * pricing.CACHE_WRITE_PRICING[model]
                ), model

    def test_bundled_yaml_loads_tool_pricing(self):
        pricing = _reload_pricing()
        assert pricing.TOOL_CALL_PRICING["web_search"] == 0.01
        assert pricing.TOOL_CALL_PRICING["code_interpreter"] == 0.03

    def test_bundled_yaml_flattens_image_pricing(self):
        pricing = _reload_pricing()
        assert pricing.IMAGE_PRICING[("gpt-image-2", "low", "1024x1024")] == 0.006
        assert pricing.IMAGE_PRICING[("gpt-image-2", "high", "1024x1024")] == 0.211
        assert pricing.IMAGE_PRICING[("gpt-image-1.5", "low", "1024x1024")] == 0.009
        assert pricing.IMAGE_PRICING[("gpt-image-1", "high", "1536x1024")] == 0.25

    def test_bundled_yaml_loads_image_defaults(self):
        pricing = _reload_pricing()
        assert pricing.IMAGE_PRICING_DEFAULTS["gpt-image-2"] == 0.053
        assert pricing.IMAGE_PRICING_DEFAULTS["gpt-image-1.5"] == 0.034

    def test_bundled_yaml_loads_tts_stt_video(self):
        pricing = _reload_pricing()
        assert pricing.TTS_PRICING_PER_CHAR["tts-1"] == 0.000015
        assert pricing.STT_PRICING_PER_MINUTE["whisper-1"] == 0.006
        assert pricing.VIDEO_PRICING_PER_SECOND["sora-2"] == {
            "default": 0.10,
            "720p": 0.10,
            "1024p": 0.10,
            "1080p": 0.10,
        }
        assert pricing.VIDEO_PRICING_PER_SECOND["sora-2-pro"] == {
            "default": 0.30,
            "720p": 0.30,
            "1024p": 0.50,
            "1080p": 0.70,
        }

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
                    cache_write_per_million: 2.0
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
                    per_second_by_resolution: { default: 0.5, 1080p: 0.9 }
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
        assert pricing.CACHED_INPUT_PRICING == {}
        assert pricing.CACHE_WRITE_PRICING == {"custom-model": 2.0}
        assert pricing.TOOL_CALL_PRICING == {"custom_tool": 0.007}
        assert pricing.IMAGE_PRICING[("fake-image", "high", "1024x1024")] == 1.23
        assert pricing.IMAGE_PRICING_DEFAULTS == {"fake-image": 0.99}
        assert pricing.UNKNOWN_CHAT_MODEL_PRICING == (42.0, 100.0)
        assert pricing.VIDEO_PRICING_PER_SECOND == {"fake-video": {"default": 0.5, "1080p": 0.9}}
        assert pricing.UNKNOWN_VIDEO_MODEL_PRICING == 1.0


class TestFastTiers:
    """Fast mode (`service_tier: "fast"` / "priority") rates from the pricing page's
    "Fast mode" tab, 2026-09-03. One flat rate per model — no long-context split."""

    def test_fast_tiers_are_pinned(self):
        pricing = _reload_pricing()
        expected = {
            # model: (input, output, cached input, cache write)
            "gpt-5.6-sol": (8.00, 40.00, 0.80, 10.00),
            "gpt-5.6-terra": (4.00, 24.00, 0.40, 5.00),
            "gpt-5.6-luna": (0.40, 2.40, 0.04, 0.50),
            "gpt-5.5": (12.50, 75.00, 1.25, None),
            "gpt-5.4": (5.00, 30.00, 0.50, None),
            "gpt-5.4-mini": (1.50, 9.00, 0.15, None),
            "gpt-5.2": (3.50, 28.00, 0.35, None),
            "gpt-5.1": (2.50, 20.00, 0.25, None),
            "gpt-5": (2.50, 20.00, 0.25, None),
            "gpt-5-mini": (0.45, 3.60, 0.045, None),
            "gpt-4.1": (3.50, 14.00, 0.875, None),
            "gpt-4.1-mini": (0.70, 2.80, 0.175, None),
            "gpt-4.1-nano": (0.20, 0.80, 0.05, None),
            "o4-mini": (2.00, 8.00, 0.50, None),
            "o3": (3.50, 14.00, 0.875, None),
            "gpt-4o": (4.25, 17.00, 2.125, None),
            "gpt-4o-mini": (0.25, 1.00, 0.125, None),
        }
        assert set(pricing.FAST_TIER_PRICING) == set(expected)
        for model, (inp, out, cached, write) in expected.items():
            tier = pricing.FAST_TIER_PRICING[model]
            assert tier["input_per_million"] == inp, model
            assert tier["output_per_million"] == out, model
            assert tier["cached_input_per_million"] == cached, model
            assert tier["cache_write_per_million"] == write, model

    def test_gpt_5_6_fast_rates_are_double_standard(self):
        pricing = _reload_pricing()
        for model in ("gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna"):
            tier = pricing.FAST_TIER_PRICING[model]
            std_in, std_out = pricing.MODEL_PRICING[model]
            assert tier["input_per_million"] == pytest.approx(2 * std_in), model
            assert tier["output_per_million"] == pytest.approx(2 * std_out), model
            assert tier["cached_input_per_million"] == pytest.approx(
                2 * pricing.CACHED_INPUT_PRICING[model]
            ), model
            assert tier["cache_write_per_million"] == pytest.approx(
                2 * pricing.CACHE_WRITE_PRICING[model]
            ), model

    def test_every_fast_model_is_a_priced_chat_model(self):
        pricing = _reload_pricing()
        assert set(pricing.FAST_TIER_PRICING) <= set(pricing.MODEL_PRICING)
        # The Pro tiers and legacy ids the page lists no Fast-mode rate for are absent.
        for model in ("gpt-5.5-pro", "gpt-5.4-pro", "gpt-5.2-pro", "gpt-5-pro", "o3-pro", "o1"):
            assert model not in pricing.FAST_TIER_PRICING
