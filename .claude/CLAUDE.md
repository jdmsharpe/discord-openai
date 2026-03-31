# Discord OpenAI Bot - Developer Reference

## Supported Entry Points

- Launcher: `python src/bot.py` remains supported and delegates to `discord_openai.bot.main`.
- Cog composition contract:

  ```python
  from discord_openai import OpenAICog

  bot.add_cog(OpenAICog(bot=bot))
  ```

## Package Layout

```text
src/
├── bot.py                           # Thin repo-local launcher
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
- The test suite is organized into module-aligned files such as `tests/test_openai_cog.py`, `tests/test_openai_embeds.py`, `tests/test_openai_responses.py`, and `tests/test_openai_tooling.py`.
- `tests/test_package_import.py` is the package import smoke test.
- New tests and patches should target real owners under `discord_openai...`.
- Examples:
  - `discord_openai.cogs.openai.tooling.OPENAI_VECTOR_STORE_IDS`
  - `discord_openai.cogs.openai.embeds.append_pricing_embed`
  - `discord_openai.cogs.openai.tooling.extract_tool_info`
- Import `OpenAICog` from `discord_openai`; do not reintroduce legacy `openai_api` shim paths.

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
