from unittest.mock import MagicMock

import pytest

from discord_openai.cogs.openai.responses import build_reasoning_config, extract_summary_text


class TestBuildReasoningConfig:
    @pytest.mark.parametrize(
        "model,effort,mode,expected",
        [
            ("gpt-5.6-sol", None, "pro", {"summary": "auto", "mode": "pro"}),
            ("gpt-5.6-sol", "max", "pro", {"effort": "max", "summary": "auto", "mode": "pro"}),
            ("gpt-5.6-sol", "none", "pro", {"effort": "none", "summary": "auto", "mode": "pro"}),
            ("gpt-5.6-sol", "medium", None, {"effort": "medium", "summary": "auto"}),
            ("gpt-5.6-sol", "medium", "standard", {"effort": "medium", "summary": "auto"}),
            ("gpt-5.6-sol", None, None, None),
            ("gpt-5.6-sol", None, "standard", None),
            ("o3", None, None, {"effort": "medium", "summary": "auto"}),
        ],
        ids=[
            "pro-no-effort",
            "pro-max",
            "pro-effort-none",
            "effort-only",
            "effort-standard-omits-mode",
            "nothing",
            "standard-alone-is-nothing",
            "o-series-default",
        ],
    )
    def test_table(self, model, effort, mode, expected):
        assert build_reasoning_config(model, effort, mode) == expected

    def test_standard_mode_is_never_emitted(self):
        """`mode: standard` must never reach the API; older models 400 on the key."""
        for effort in (None, "none", "medium"):
            config = build_reasoning_config("gpt-5.5", effort, "standard") or {}
            assert "mode" not in config


class TestExtractSummaryText:
    def test_single_reasoning_block(self):
        response = MagicMock()
        summary_block = MagicMock()
        summary_block.type = "summary_text"
        summary_block.text = "The model considered multiple approaches."
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [summary_block]
        response.output = [reasoning_item]
        result = extract_summary_text(response)
        assert result == "The model considered multiple approaches."

    def test_multiple_summary_blocks(self):
        response = MagicMock()
        block1 = MagicMock()
        block1.type = "summary_text"
        block1.text = "First thought."
        block2 = MagicMock()
        block2.type = "summary_text"
        block2.text = "Second thought."
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [block1, block2]
        response.output = [reasoning_item]
        result = extract_summary_text(response)
        assert result == "First thought.\n\nSecond thought."

    def test_no_reasoning_items(self):
        response = MagicMock()
        message_item = MagicMock()
        message_item.type = "message"
        response.output = [message_item]
        assert extract_summary_text(response) == ""

    def test_empty_output(self):
        response = MagicMock()
        response.output = []
        assert extract_summary_text(response) == ""

    def test_none_output(self):
        response = MagicMock()
        response.output = None
        assert extract_summary_text(response) == ""

    def test_reasoning_with_none_summary(self):
        response = MagicMock()
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = None
        response.output = [reasoning_item]
        assert extract_summary_text(response) == ""

    def test_summary_block_with_none_text(self):
        response = MagicMock()
        block = MagicMock()
        block.type = "summary_text"
        block.text = None
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [block]
        response.output = [reasoning_item]
        assert extract_summary_text(response) == ""

    def test_non_summary_text_blocks_ignored(self):
        response = MagicMock()
        block = MagicMock()
        block.type = "other_type"
        block.text = "Should be ignored"
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [block]
        response.output = [reasoning_item]
        assert extract_summary_text(response) == ""

    def test_mixed_output_items(self):
        response = MagicMock()
        block = MagicMock()
        block.type = "summary_text"
        block.text = "Reasoning output"
        reasoning_item = MagicMock()
        reasoning_item.type = "reasoning"
        reasoning_item.summary = [block]
        message_item = MagicMock()
        message_item.type = "message"
        response.output = [reasoning_item, message_item]
        assert extract_summary_text(response) == "Reasoning output"
