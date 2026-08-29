from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from discord_openai.cogs.openai.state import prune_runtime_state, track_daily_cost
from discord_openai.util import ResponseParameters, calculate_cost


@pytest.mark.asyncio
async def test_prune_runtime_state_removes_stale_entries_and_preserves_active_entries():
    now = datetime.now(UTC)
    stale_conversation = ResponseParameters(
        model="gpt-5.4",
        input=[],
        conversation_starter_id=11,
        channel_id=100,
        conversation_id=1,
        updated_at=now - timedelta(hours=13),
    )
    active_conversation = ResponseParameters(
        model="gpt-5.4",
        input=[],
        conversation_starter_id=22,
        channel_id=100,
        conversation_id=2,
        updated_at=now - timedelta(minutes=10),
    )

    stale_message = MagicMock()
    stale_message.edit = AsyncMock()
    orphan_message = MagicMock()
    orphan_message.edit = AsyncMock()
    active_message = MagicMock()
    active_message.edit = AsyncMock()

    old_day = (date.today() - timedelta(days=31)).isoformat()
    today = date.today().isoformat()

    cog = SimpleNamespace(
        logger=MagicMock(),
        conversation_histories={1: stale_conversation, 2: active_conversation},
        views={
            1: (11, MagicMock(), now),
            2: (22, MagicMock(), now),
            3: (33, MagicMock(), now),
        },
        last_view_messages={
            1: (11, stale_message, now),
            2: (22, active_message, now),
            3: (33, orphan_message, now),
        },
        daily_costs={
            (11, old_day): (2.5, now - timedelta(days=31)),
            (22, today): (1.0, now),
        },
    )

    await prune_runtime_state(cog)

    assert set(cog.conversation_histories) == {2}
    assert set(cog.views) == {2}
    assert set(cog.last_view_messages) == {2}
    stale_message.edit.assert_awaited_once_with(view=None)
    orphan_message.edit.assert_awaited_once_with(view=None)
    active_message.edit.assert_not_awaited()
    assert (11, old_day) not in cog.daily_costs
    assert (22, today) in cog.daily_costs


def test_track_daily_cost_bills_cache_write_tokens():
    cog = SimpleNamespace(logger=MagicMock(), daily_costs={})

    total = track_daily_cost(cog, 11, "gpt-5.6-sol", 1_000, 0, cache_write_tokens=1_000)

    assert total == pytest.approx(calculate_cost("gpt-5.6-sol", 1_000, 0, 0, 1_000))
    assert total > calculate_cost("gpt-5.6-sol", 1_000, 0)
    assert "cache_write_tokens=1000" in cog.logger.info.call_args.args[0]
