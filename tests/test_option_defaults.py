"""Guard against a slash-command option's ``(default: X)`` clause naming the wrong choice.

Discord renders an option's ``description`` verbatim in the command picker, so a
description advertising ``(default: GPT Image 1)`` while the code actually defaults to
``gpt-image-2`` shows **wrong information to every user** — silently, forever, with
nothing in the logs to notice. It is a documentation bug only users ever see, which is
why no runtime check catches it. Every instance found in this fleet traced back to the
same move: a "promote the new default" commit that changed ``default=`` and missed the
``(default: ...)`` clause sitting a few characters away in the same decorator.

Acceptance is deliberately strict — see :func:`_claim_matches`. Plain substring
containment is not enough in **either** direction, and both holes are now closed:

* a claim that is a strict PREFIX of the real display name is drift, not a match —
  promoting ``"Foo 1"`` to ``"Foo 1.5"`` leaves the description still saying ``"Foo 1"``,
  and a ``display_name.startswith(claim)`` rule waves through precisely the case this
  guard exists to catch;
* a claim that EXTENDS the real display name is drift too — ``"Claude Opus 5"`` is a
  substring of a claim reading ``"Claude Opus 5.1"``, so promoting ``5`` to ``5.1``
  while leaving a stale description behind used to pass.

Every match is therefore anchored with :data:`NOT_EXTENDED`, a lookahead rejecting a
continuation into a longer identifier — a word character, a hyphen, or a dot followed by
a digit — while still allowing ordinary sentence punctuation, because real descriptions
write things like ``"(default: Claude Opus 5. warning: Opus is expensive!)"``. The
raw-value spelling is accepted only when the value is non-empty, because an empty needle
matches everywhere and would otherwise accept arbitrary wrong text.

Scope is narrow on purpose. An option is asserted over only when it has ``choices`` AND
a non-``None`` ``default`` AND a ``(default: X)`` clause AND that default resolves to one
of its own choices — the one shape where the truth is fully introspectable. An option
whose default resolves to no listed choice has no display name to compare against: it is
counted as UNASSERTABLE and reported, never quietly passed. Options with no ``choices``,
or with ``default=None``, are out of scope entirely — their effective default is applied
downstream in the handler where introspection cannot see it, and asserting over them
produced roughly 35 false alarms across the fleet. A noisy guard gets muted, and a muted
guard is worse than none; do not widen this.

Three tests follow, in order:

* the MATCHER test pins the acceptance rule itself against a fixed case table, so the
  rule stays under test regardless of what discovery finds;
* the DISCOVERY test pins the exact number of options discovery must find, so a partial
  collapse of the walk cannot hide behind a still-green suite;
* the per-option test runs the acceptance rule over every option discovered on the cog.
"""

import re

import discord
import pytest

from discord_openai.cogs.openai.cog import OpenAICog

#: Matches the ``(default: X)`` clause conventionally used in option descriptions.
DEFAULT_CLAIM_RE = re.compile(r"\(default:\s*([^)]+)\)", re.I)

#: Strips a trailing parenthetical: ``"Sora 2 (Fast)"`` -> ``"Sora 2"``.
PARENTHETICAL_RE = re.compile(r"\s*\(.*")

#: Anchors every match so the claim may not CONTINUE the matched text into a longer
#: identifier. ``(?![\w-])`` rejects a word character or hyphen; ``(?!\.\d)`` rejects a
#: version dot such as the ``.1`` in ``"Claude Opus 5.1"``. A bare ``.`` followed by a
#: space, a ``;``, a ``!`` and the rest of ordinary prose still matches, which is what
#: lets a correct description read ``"(default: Claude Opus 5. warning: ...)"``.
#: Deleting this constant reopens the superset hole; loosening it to ``(?!\w)`` reopens
#: the hyphenated-id half of it.
NOT_EXTENDED = r"(?![\w-])(?!\.\d)(?!\s+\w)"


def _claim_matches(claimed: str, display_name: str, value: object) -> bool:
    """Return whether ``claimed`` is a legitimate spelling of the real default.

    Exactly four spellings are accepted, each observed in descriptions that are correct,
    and each anchored with :data:`NOT_EXTENDED` so the claim cannot extend past the text
    it matched:

    * the display name appears in the claim (``"Auto"`` claimed as ``"auto"``);
    * the claim equals the display name's stem — the name with any trailing parenthetical
      removed (``"Marin (Only supported with ...)"`` claimed as ``"Marin"``);
    * the claim starts with that stem, because descriptions sometimes append prose after
      the name (``"Deep Research; Max for best reports"``);
    * the raw default value is non-empty and appears in the claim, because descriptions
      often quote the value (``"1280x720"``) where the name is ``"Landscape (1280x720)"``.

    Nothing else. Two rejections carry the whole guard and must not be relaxed: a claim
    that is a strict prefix of the display name (a stale ``"Foo 1"`` after the default
    became ``"Foo 1.5"``), and a claim that extends it (a stale ``"Claude Opus 5"``
    description left behind by a promotion to ``"Claude Opus 5.1"``, which plain
    containment accepted).
    """
    name = (display_name or "").strip().lower()
    raw = str(value or "").strip().lower()
    claim = (claimed or "").strip().lower()
    if not name or not claim:
        return False
    stem = PARENTHETICAL_RE.sub("", name).strip()
    if re.search(re.escape(name) + NOT_EXTENDED, claim):
        return True
    if stem and claim == stem:
        return True
    if stem and re.match(re.escape(stem) + NOT_EXTENDED, claim):
        return True
    if raw and re.search(re.escape(raw) + NOT_EXTENDED, claim):  # noqa: SIM103
        return True
    # Kept as four parallel branches rather than one inlined boolean: each branch is one
    # of the four documented spellings, each carrying NOT_EXTENDED, and the shape is what
    # makes an added fifth branch obvious in review.
    return False


#: ``(display name, raw value, claimed text, expected acceptance, why this case exists)``
#:
#: A fixed table, shared verbatim across the fleet, that keeps the acceptance rule under
#: test independently of discovery — no rename, refactor, or py-cord change can render
#: this parametrization empty. It pins both directions of the containment hole (the
#: prefix case and the superset case) plus the sentence-punctuation case that stops the
#: fix from being over-tightened into flagging correct descriptions.
MATCHER_CASES = [
    (
        "Gemini 3.7 Flash",
        "gemini-3.7-flash",
        "Gemini 3.7 Flash Pro",
        False,
        "space-extended superset drift: the claim names a longer, different model",
    ),
    ("GPT Image 2", "gpt-image-2", "GPT Image 1.5", False, "real drift"),
    ("GPT Image 1.5", "gpt-image-1.5", "GPT Image 1", False, "prefix-superset drift (v3 hole)"),
    ("Claude Opus 5", "claude-opus-5", "Claude Opus 5.1", False, "SUPERSET drift (v4 hole)"),
    (
        "Claude Opus 5",
        "claude-opus-5",
        "Claude Opus 5. warning: Opus is expensive!",
        True,
        "sentence punctuation after name",
    ),
    (
        "Grok Imagine Video 1.5 (Preview)",
        "grok-imagine-video-1.5-preview",
        "Grok Imagine Video 1.5",
        True,
        "trailing parenthetical trimmed",
    ),
    (
        "Deep Research (Apr 2026)",
        "deep-research-preview-04-2026",
        "Deep Research; Max for best reports",
        True,
        "prose after the stem",
    ),
    ("Square (1:1)", "1:1", "1:1", True, "description uses the raw value"),
    ("Kore (Firm)", "Kore", "Kore", True, "value spelling"),
    ("Gemini 3.7 Flash", "gemini-3.7-flash", "Gemini 3.6 Flash", False, "real drift"),
    ("Anything", "", "total nonsense", False, "empty value must not vacuously accept"),
    (
        "Gemini 3.1 Flash Preview TTS",
        "gemini-3.1-flash-tts-preview",
        "Gemini 2.5 Flash Preview TTS",
        False,
        "real drift",
    ),
]

MATCHER_IDS = [
    "reject-space-extended-superset-drift",
    "reject-drift-gpt-image-2-claimed-1.5",
    "reject-prefix-drift-1.5-claimed-1",
    "reject-superset-drift-opus-5-claimed-5.1",
    "accept-sentence-punctuation-after-name",
    "accept-trailing-parenthetical-trim",
    "accept-prose-after-stem",
    "accept-raw-value-square-1to1",
    "accept-value-spelling-kore",
    "reject-drift-gemini-3.7-claimed-3.6",
    "reject-empty-value-nonsense-claim",
    "reject-drift-gemini-3.1-tts-claimed-2.5",
]


@pytest.mark.parametrize("display_name,value,claimed,expected,why", MATCHER_CASES, ids=MATCHER_IDS)
def test_claim_matcher_accepts_only_legitimate_spellings(
    display_name, value, claimed, expected, why
):
    """Pin the acceptance rule itself, so the guard can never be quietly declawed.

    The per-option test below only ever exercises the spellings this repo happens to use
    today; loosening ``_claim_matches`` would keep it green while the guard stopped
    guarding. These cases fail the moment the rule drifts either way — too permissive
    (real drift accepted) or too strict (a correct description flagged).
    """
    assert _claim_matches(claimed, display_name, value) is expected, (
        f"_claim_matches({claimed!r}, {display_name!r}, {value!r}) should be {expected} "
        f"({why}). The acceptance rule is exactly four conditions — display name in the "
        "claim; claim equals the name's stem; claim starts with that stem; or a non-empty "
        "raw value in the claim — each anchored with NOT_EXTENDED. Adding a fifth "
        "condition (especially display_name.startswith(claim)) reopens the prefix hole; "
        "dropping the NOT_EXTENDED lookahead reopens the superset hole."
    )


def _discover_default_claims():
    """Return ``(assertable, unassertable)`` for options whose description states a default.

    Walks ``OpenAICog``'s :class:`discord.SlashCommandGroup` attributes, then their
    subcommands, then each subcommand's options — so future commands and options are
    guarded automatically without touching this test.

    ``assertable`` holds ``(path, claimed, value, display_name)`` for options whose
    default resolves to one of their own choices. ``unassertable`` holds ``(path, value)``
    for the rest: their default names no listed choice, so there is no display name to
    compare the claim against. Those are reported, not folded into the passing set.
    """
    assertable, unassertable = [], []
    for group in vars(OpenAICog).values():
        if not isinstance(group, discord.SlashCommandGroup):
            continue
        for subcommand in group.subcommands:
            for opt in getattr(subcommand, "options", []):
                choices = getattr(opt, "choices", None) or []
                value = getattr(opt, "default", None)
                if not choices or value is None:
                    continue
                claim = DEFAULT_CLAIM_RE.search(getattr(opt, "description", "") or "")
                if not claim:
                    continue
                path = f"/{group.name} {subcommand.name} {opt.name}"
                display_name = next((c.name for c in choices if c.value == value), None)
                if display_name is None:
                    unassertable.append((path, value))
                    continue
                assertable.append((path, claim.group(1).strip(), value, display_name))
    return sorted(assertable), sorted(unassertable)


DEFAULT_CLAIMS, UNASSERTABLE_OPTIONS = _discover_default_claims()

#: The EXACT option counts discovery must find on this cog today.
#:
#: These are exact, not floors, and that is the whole point. A ``>= N`` bound in a repo
#: whose real count IS N can only fire when discovery returns *nothing much*, which makes
#: it behaviourally identical to a bare non-emptiness check — and a floor written ``>= 0``
#: can never fire at all. Pinning the exact numbers is what turns a PARTIAL collapse
#: (a renamed cog attribute, a py-cord change to where options hang off subcommands, a
#: description that stopped using the ``(default: X)`` convention) into a red test instead
#: of a silently thinned parametrization that still reports "passed".
#:
#: NEXT CONTRIBUTOR: when you add or remove a choice-backed option with a stated default,
#: UPDATE THESE NUMBERS DELIBERATELY in the same commit. A mismatch means one of exactly
#: two things — a real change to the command surface, or a discovery regression — and both
#: deserve a human look before the number moves. Never "fix" a mismatch by relaxing the
#: comparison back to an inequality.
EXPECTED_ASSERTABLE_OPTIONS = 13
EXPECTED_UNASSERTABLE_OPTIONS = 0


def test_discovery_finds_exactly_the_recorded_options():
    """Fail if discovery finds a different number of options than this repo records."""
    assert (len(DEFAULT_CLAIMS), len(UNASSERTABLE_OPTIONS)) == (
        EXPECTED_ASSERTABLE_OPTIONS,
        EXPECTED_UNASSERTABLE_OPTIONS,
    ), (
        f"discovery found {len(DEFAULT_CLAIMS)} assertable and "
        f"{len(UNASSERTABLE_OPTIONS)} unassertable option(s) on OpenAICog, but this repo "
        f"records {EXPECTED_ASSERTABLE_OPTIONS} and {EXPECTED_UNASSERTABLE_OPTIONS}. "
        f"Assertable: {[path for path, *_ in DEFAULT_CLAIMS]}. "
        f"Unassertable: {UNASSERTABLE_OPTIONS}. Either the command surface really changed "
        "— in which case update EXPECTED_ASSERTABLE_OPTIONS / "
        "EXPECTED_UNASSERTABLE_OPTIONS in the same commit — or discovery regressed: check "
        "that OpenAICog still exposes SlashCommandGroup attributes, that options still "
        "hang off subcommand.options, and that descriptions still use the '(default: X)' "
        "convention. A rising unassertable count means an option's default no longer "
        "resolves to any of its own choices."
    )


@pytest.mark.parametrize(
    "path,claimed,value,display_name",
    DEFAULT_CLAIMS,
    ids=[path.lstrip("/").replace(" ", ".") for path, *_ in DEFAULT_CLAIMS],
)
def test_stated_default_names_the_real_default(path, claimed, value, display_name):
    assert _claim_matches(claimed, display_name, value), (
        f"{path} advertises '(default: {claimed})' but the option actually defaults to "
        f"{value!r}, whose choice is named {display_name!r}. Discord shows that "
        "description verbatim in the command picker, so users are being told the wrong "
        "default. Update the description to name the real default (or change default= "
        "back if the description was right)."
    )
