"""Attachments and generated speech stay in memory, so concurrent requests cannot share a file."""

import asyncio
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from discord_openai.cogs.openai.image import run_image_command
from discord_openai.cogs.openai.speech import run_stt_command, run_tts_command
from discord_openai.util import fetch_attachment_bytes


@pytest.fixture
def disk(monkeypatch, tmp_path: Path):
    """Point the temp directory and the working directory at empty read-only directories.

    Any attempt to write a file there raises, so a command that writes to disk
    replies with an error embed instead of the expected result.
    """
    temp_root = tmp_path / "temp-root"
    cwd = tmp_path / "cwd"
    temp_root.mkdir()
    cwd.mkdir()
    monkeypatch.setattr(tempfile, "tempdir", str(temp_root))
    monkeypatch.chdir(cwd)
    temp_root.chmod(0o500)
    cwd.chmod(0o500)
    yield [temp_root, cwd]
    temp_root.chmod(0o700)
    cwd.chmod(0o700)


def _files_on(disk: list[Path]) -> list[Path]:
    return [entry for directory in disk for entry in directory.iterdir()]


class _FakeResponse:
    def __init__(self, status: int, body: bytes):
        self.status = status
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def read(self) -> bytes:
        # Yield to the event loop so concurrent downloads interleave.
        await asyncio.sleep(0)
        return self._body


class _FakeSession:
    def __init__(self, bodies: dict[str, bytes], status: int = 200):
        self._bodies = bodies
        self._status = status

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    def get(self, url: str) -> _FakeResponse:
        return _FakeResponse(self._status, self._bodies.get(url, b""))


def _patch_session(bodies: dict[str, bytes], status: int = 200):
    return patch(
        "discord_openai.util.aiohttp.ClientSession",
        new=lambda: _FakeSession(bodies, status),
    )


def _ctx():
    return SimpleNamespace(
        author=SimpleNamespace(id=1234),
        defer=AsyncMock(),
        send_followup=AsyncMock(return_value=MagicMock()),
    )


def _sent_file(ctx):
    files = [
        call.kwargs["file"]
        for call in ctx.send_followup.await_args_list
        if call.kwargs.get("file") is not None
    ]
    assert len(files) == 1
    return files[0]


def _speech_cog(**audio):
    return SimpleNamespace(
        logger=MagicMock(),
        openai_client=SimpleNamespace(audio=SimpleNamespace(**audio)),
        _track_daily_cost_direct=MagicMock(return_value=0.01),
    )


def _voice_attachment(url: str):
    return SimpleNamespace(url=url, filename="voice-message.ogg", size=4096)


class TestFetchAttachmentBytes:
    @pytest.mark.asyncio
    async def test_returns_the_body(self):
        with _patch_session({"https://cdn.example/x": b"data"}):
            assert await fetch_attachment_bytes("https://cdn.example/x") == b"data"

    @pytest.mark.asyncio
    async def test_failed_download_raises(self):
        with (
            _patch_session({}, status=404),
            pytest.raises(Exception, match="status 404"),
        ):
            await fetch_attachment_bytes("https://cdn.example/missing")


class TestSpeechToText:
    @pytest.mark.asyncio
    async def test_concurrent_voice_messages_each_send_their_own_audio(self, disk):
        """Discord names every voice message voice-message.ogg."""
        create = AsyncMock(return_value=SimpleNamespace(text="hello"))
        cog = _speech_cog(transcriptions=SimpleNamespace(create=create))
        first_ctx, second_ctx = _ctx(), _ctx()
        bodies = {"https://cdn.example/a": b"first user audio", "https://cdn.example/b": b"second"}

        with _patch_session(bodies):
            await asyncio.gather(
                run_stt_command(
                    cog,
                    first_ctx,
                    _voice_attachment("https://cdn.example/a"),
                    model="gpt-transcribe",
                    action="transcription",
                ),
                run_stt_command(
                    cog,
                    second_ctx,
                    _voice_attachment("https://cdn.example/b"),
                    model="gpt-transcribe",
                    action="transcription",
                ),
            )

        sent = sorted(call.kwargs["file"] for call in create.await_args_list)
        assert sent == [
            ("voice-message.ogg", b"first user audio"),
            ("voice-message.ogg", b"second"),
        ]
        first_reply, second_reply = _sent_file(first_ctx), _sent_file(second_ctx)
        assert first_reply.filename == second_reply.filename == "voice-message.ogg"
        assert first_reply.fp.read() == b"first user audio"
        assert second_reply.fp.read() == b"second"
        assert _files_on(disk) == []

    @pytest.mark.asyncio
    async def test_diarized_transcription_sends_the_attachment_bytes(self, disk):
        create = AsyncMock(return_value=SimpleNamespace(text="hello", segments=None))
        cog = _speech_cog(transcriptions=SimpleNamespace(create=create))
        ctx = _ctx()

        with _patch_session({"https://cdn.example/a": b"ogg bytes"}):
            await run_stt_command(
                cog,
                ctx,
                _voice_attachment("https://cdn.example/a"),
                model="gpt-4o-transcribe-diarize",
                action="transcription",
            )

        kwargs = create.await_args.kwargs
        assert kwargs["file"] == ("voice-message.ogg", b"ogg bytes")
        assert kwargs["chunking_strategy"] == "auto"
        assert kwargs["response_format"] == "diarized_json"
        assert _sent_file(ctx).fp.read() == b"ogg bytes"

    @pytest.mark.asyncio
    async def test_failed_download_replies_with_an_error(self, disk):
        create = AsyncMock()
        cog = _speech_cog(transcriptions=SimpleNamespace(create=create))
        ctx = _ctx()

        with _patch_session({}, status=404):
            await run_stt_command(
                cog,
                ctx,
                _voice_attachment("https://cdn.example/missing"),
                model="gpt-transcribe",
                action="transcription",
            )

        create.assert_not_awaited()
        embed = ctx.send_followup.await_args.kwargs["embed"]
        assert "Failed to download the attachment (status 404)." in embed.description

    @pytest.mark.asyncio
    async def test_translation_sends_the_attachment_bytes(self, disk):
        create = AsyncMock(return_value=SimpleNamespace(text="hello"))
        cog = _speech_cog(translations=SimpleNamespace(create=create))
        ctx = _ctx()

        with _patch_session({"https://cdn.example/a": b"ogg bytes"}):
            await run_stt_command(
                cog,
                ctx,
                _voice_attachment("https://cdn.example/a"),
                model="gpt-transcribe",
                action="translation",
            )

        assert create.await_args.kwargs["file"] == ("voice-message.ogg", b"ogg bytes")
        assert _files_on(disk) == []


class TestTextToSpeech:
    @pytest.mark.asyncio
    async def test_reply_attaches_the_response_audio_without_writing_a_file(self, disk):
        # No write_to_file attribute: calling it would raise AttributeError.
        create = AsyncMock(return_value=SimpleNamespace(content=b"mp3 bytes"))
        cog = _speech_cog(speech=SimpleNamespace(create=create))
        ctx = _ctx()

        await run_tts_command(cog, ctx, "Hi", "gpt-4o-mini-tts", "marin", "", "mp3", 1.0)

        reply = _sent_file(ctx)
        assert reply.filename == "marin_speech.mp3"
        assert reply.fp.read() == b"mp3 bytes"
        assert _files_on(disk) == []


class TestImageEdit:
    @pytest.mark.asyncio
    async def test_edit_sends_the_attachment_bytes(self, disk):
        edit = AsyncMock(side_effect=RuntimeError("stop after request"))
        cog = SimpleNamespace(
            logger=MagicMock(),
            openai_client=SimpleNamespace(images=SimpleNamespace(edit=edit)),
            _track_daily_cost_direct=MagicMock(return_value=0.01),
        )
        attachment = SimpleNamespace(
            url="https://cdn.example/image", filename="image.png", content_type="image/png"
        )

        with _patch_session({"https://cdn.example/image": b"png bytes"}):
            await run_image_command(
                cog,
                _ctx(),
                prompt="Make it blue",
                model="gpt-image-2.5-sunburst",
                quality="low",
                size="1024x1024",
                attachment=attachment,
            )

        assert edit.await_args.kwargs["image"] == ("image.png", b"png bytes")
        assert _files_on(disk) == []
