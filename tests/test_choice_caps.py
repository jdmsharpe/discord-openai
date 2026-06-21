"""Guard against breaching Discord's 25-static-choices-per-option cap.

Discord rejects any slash-command option carrying more than 25 static
``choices`` entries with API error ``50035``. py-cord syncs every command in a
single all-or-nothing bulk ``PUT`` on ``on_connect``, so ONE over-limit list
silently aborts slash-command registration for EVERY cog — surfacing only as an
``Ignoring exception in on_connect`` log line. This test fails loudly in CI
before that can ship.

It is deliberately generic: it discovers every module-level ``*_CHOICES`` list
in :mod:`discord_openai.cogs.openai.command_options` at import time and asserts
each holds ``<= 25`` entries. New menus are covered automatically the moment
they are added; no edit to this file is required. Because it counts the
already-RESOLVED module-level lists, any computed/generated choices lists are
measured at their true runtime length with zero AST machinery.
"""

import pytest

from discord_openai.cogs.openai import command_options

DISCORD_MAX_STATIC_CHOICES = 25


def _discover_choice_lists():
    """Return ``(name, list)`` pairs for every module-level ``*_CHOICES`` list.

    Discovery is dynamic so any future menu added to ``command_options`` is
    guarded automatically without touching this test.
    """
    found = [
        (name, value)
        for name, value in vars(command_options).items()
        if name.endswith("_CHOICES") and isinstance(value, list)
    ]
    assert found, (
        "no *_CHOICES lists discovered in "
        "discord_openai.cogs.openai.command_options — the guard would silently "
        "protect nothing; check the module path and naming convention"
    )
    return sorted(found)


CHOICE_LISTS = _discover_choice_lists()


@pytest.mark.parametrize("name,choices", CHOICE_LISTS, ids=[n for n, _ in CHOICE_LISTS])
def test_choice_list_within_discord_cap(name, choices):
    count = len(choices)
    assert count <= DISCORD_MAX_STATIC_CHOICES, (
        f"{name} has {count} choices (> {DISCORD_MAX_STATIC_CHOICES}). "
        "Discord rejects any slash-command option with more than 25 static "
        "choices (API error 50035), and py-cord's all-or-nothing bulk sync "
        "means this single over-limit list aborts slash-command registration "
        "for EVERY cog. Drop a deprecated entry or switch the option from "
        "choices= to an autocomplete= callback (which has no length limit)."
    )
