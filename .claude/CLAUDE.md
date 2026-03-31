# Discord OpenAI Bot - Developer Reference

## Supported Entry Points

- Launcher: `python src/bot.py` remains supported and delegates to `discord_openai.bot.main`.
- Cog composition contract:

  ```python
  from discord_openai import OpenAICog

  bot.add_cog(OpenAICog(bot=bot))
  ```

- Legacy shim: `src/openai_api.py` exists only for import compatibility, emits a `DeprecationWarning`, and re-exports `OpenAICog` without preserving `OpenAIAPI`.

## Package Layout

```text
src/
├── bot.py                           # Thin repo-local launcher
├── openai_api.py                    # Temporary compatibility shim
└── discord_openai/
    ├── __init__.py                  # Re-exports OpenAICog
    ├── bot.py                       # Namespaced launcher
    ├── util.py
    ├── config/
    │   ├── __init__.py
    │   └── auth.py
    └── cogs/openai/
        ├── __init__.py
        ├── attachments.py
        ├── chat.py
        ├── client.py
        ├── cog.py
        ├── embeds.py
        ├── image.py
        ├── models.py
        ├── research.py
        ├── responses.py
        ├── speech.py
        ├── state.py
        ├── tooling.py
        ├── video.py
        └── views.py
```

Top-level `button_view.py`, `util.py`, and `config/` remain repo-local implementation details and are not part of the installed public API.

## Testing And Patch Targets

- `pytest` runs with `pythonpath = ["src"]`.
- New tests and patches should target real owners under `discord_openai...`, not `openai_api`.
- Examples:
  - `discord_openai.cogs.openai.tooling.OPENAI_VECTOR_STORE_IDS`
  - `discord_openai.cogs.openai.embeds.append_pricing_embed`
  - `discord_openai.cogs.openai.tooling.extract_tool_info`
- `tests/test_openai_api_shim.py` is the only place that should intentionally import `openai_api`.

## Validation Commands

```bash
ruff check src/ tests/
ruff format src/ tests/
pyright src/
pytest -q
```

## Provider Notes

- `resolve_selected_tools()` in `discord_openai.cogs.openai.tooling` remains the canonical tool-resolution path for chat and research.
- `file_search` requires `OPENAI_VECTOR_STORE_IDS`.
- `shell` remains limited to GPT-5 series models.
- `ResponseParameters.to_dict()` in `discord_openai.util` remains the canonical request-construction path.
