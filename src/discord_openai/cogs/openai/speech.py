import tempfile
from pathlib import Path
from typing import Any, cast

from discord import ApplicationContext, Attachment, Colour, Embed, File

from ...config.auth import SHOW_COST_EMBEDS
from ...util import (
    calculate_stt_cost,
    calculate_tts_cost,
    download_attachment,
    estimate_audio_duration_seconds,
    format_openai_error,
    truncate_text,
)
from .embeds import append_flat_pricing_embed, error_embed
from .models import TextToSpeechParameters


async def run_tts_command(
    cog,
    ctx: ApplicationContext,
    input: str,
    model: str,
    voice: str,
    instructions: str,
    response_format: str,
    speed: float,
) -> None:
    """Run the /openai tts command."""
    await ctx.defer()

    params = TextToSpeechParameters(input, model, voice, instructions, response_format, speed)
    speech_file_path = None
    try:
        response = await cog.openai_client.audio.speech.create(**params.to_dict())
        speech_file_path = Path(tempfile.gettempdir()) / f"{voice}_speech.{response_format}"
        response.write_to_file(speech_file_path)

        description = (
            f"**Text:** {truncate_text(params.input, 1500)}\n"
            f"**Model:** {params.model}\n"
            f"**Voice:** {params.voice}\n"
            + (
                f"**Instructions:** {truncate_text(instructions, 500)}\n"
                if params.instructions
                else ""
            )
            + f"**Response Format:** {response_format}\n"
            + f"**Speed:** {params.speed}\n"
        )

        embed = Embed(
            title="Text-to-Speech Generation",
            description=description,
            color=Colour.blue(),
        )

        embeds = [embed]
        tts_cost = calculate_tts_cost(model, len(input))
        daily_cost = cog._track_daily_cost_direct(
            ctx.author.id,
            "tts",
            model,
            tts_cost,
            f"characters={len(input)} | voice={params.voice}",
        )
        if SHOW_COST_EMBEDS:
            append_flat_pricing_embed(
                embeds,
                tts_cost,
                daily_cost,
                f"{len(input):,} chars · {params.voice}",
            )

        await ctx.send_followup(embeds=embeds, file=File(speech_file_path))
    except Exception as e:
        await ctx.send_followup(embed=error_embed(format_openai_error(e)))
    finally:
        if speech_file_path and speech_file_path.exists():
            speech_file_path.unlink(missing_ok=True)


async def run_stt_command(
    cog,
    ctx: ApplicationContext,
    attachment: Attachment,
    model: str,
    action: str,
) -> None:
    """Run the /openai stt command."""
    await ctx.defer()

    speech_file_path = None
    try:
        speech_file_path = await download_attachment(attachment.url, attachment.filename)
        with open(speech_file_path, "rb") as speech_file:
            if action == "transcription":
                if model == "gpt-4o-transcribe-diarize":
                    response = await cog.openai_client.audio.transcriptions.create(
                        model=model,
                        file=speech_file,
                        chunking_strategy=cast(Any, "auto"),
                        response_format=cast(Any, "diarized_json"),
                    )
                else:
                    response = await cog.openai_client.audio.transcriptions.create(
                        model=model,
                        file=speech_file,
                    )
            else:
                response = await cog.openai_client.audio.translations.create(
                    model="whisper-1",
                    file=speech_file,
                )

        segments = getattr(response, "segments", None)
        if model == "gpt-4o-transcribe-diarize" and segments:
            lines = []
            for seg in segments:
                speaker = getattr(seg, "speaker", "Unknown")
                text = getattr(seg, "text", "").strip()
                if text:
                    lines.append(f"**{speaker}:** {text}")
            transcription_text = truncate_text("\n".join(lines), 3500)
        else:
            transcription_text = truncate_text(getattr(response, "text", None), 3500)
        description = (
            f"**Model:** {model}\n"
            + f"**Action:** {action}\n"
            + (f"**Output:**\n{transcription_text}\n" if transcription_text else "")
        )
        embed = Embed(title="Speech-to-Text", description=description, color=Colour.blue())

        embeds = [embed]
        actual_model = "whisper-1" if action != "transcription" else model
        est_duration = estimate_audio_duration_seconds(attachment.size, attachment.filename)
        stt_cost = calculate_stt_cost(actual_model, est_duration)
        daily_cost = cog._track_daily_cost_direct(
            ctx.author.id,
            "stt",
            actual_model,
            stt_cost,
            f"file={attachment.filename} | size={attachment.size}"
            f" | est_duration={est_duration:.1f}s",
        )
        if SHOW_COST_EMBEDS:
            append_flat_pricing_embed(
                embeds,
                stt_cost,
                daily_cost,
                f"~{est_duration:.0f}s audio · {actual_model}",
            )

        await ctx.send_followup(embeds=embeds, file=File(speech_file_path))
    except Exception as e:
        await ctx.send_followup(embed=error_embed(format_openai_error(e)))
    finally:
        if speech_file_path and speech_file_path.exists():
            speech_file_path.unlink(missing_ok=True)
