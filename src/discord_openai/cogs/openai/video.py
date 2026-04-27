import asyncio
import tempfile
from pathlib import Path

from discord import ApplicationContext, Colour, Embed, File

from ...config.auth import SHOW_COST_EMBEDS
from ...util import calculate_video_cost, format_openai_error, truncate_text
from .embed_delivery import send_embed_batches
from .embeds import append_flat_pricing_embed, error_embed
from .models import VideoGenerationParameters


async def run_video_command(
    cog,
    ctx: ApplicationContext,
    prompt: str,
    model: str,
    size: str,
    seconds: str,
) -> None:
    """Run the /openai video command."""
    await ctx.defer()

    if size in ("1920x1080", "1080x1920") and model != "sora-2-pro":
        await send_embed_batches(
            ctx.send_followup,
            embed=error_embed(
                "1080p resolutions (1920x1080, 1080x1920) are only supported with Sora 2 Pro."
            ),
            logger=cog.logger,
        )
        return

    video_params = VideoGenerationParameters(
        prompt=prompt,
        model=model,
        size=size,
        seconds=seconds,
    )

    video_file_path = None
    try:
        cog.logger.info(f"Starting video generation with model {model}")
        video = await cog.openai_client.videos.create(**video_params.to_dict())
        cog.logger.info(f"Video job started: {video.id}, status: {video.status}")

        poll_count = 0
        max_polls = 60
        while video.status in ("queued", "in_progress"):
            if poll_count >= max_polls:
                raise Exception("Video generation timed out after 10 minutes")

            await asyncio.sleep(10)
            video = await cog.openai_client.videos.retrieve(video.id)
            progress = video.progress if hasattr(video, "progress") and video.progress else 0
            poll_count += 1
            cog.logger.debug(f"Poll {poll_count}: status={video.status}, progress={progress}%")

        if video.status == "failed":
            raise Exception("Video generation failed. Please try a different prompt.")
        if video.status != "completed":
            raise Exception(f"Unexpected video status: {video.status}")

        content = await cog.openai_client.videos.download_content(video.id)
        video_bytes = await content.aread()
        video_file_path = Path(tempfile.gettempdir()) / f"video_{video.id}.mp4"
        video_file_path.write_bytes(video_bytes)

        description = f"**Prompt:** {truncate_text(video_params.prompt, 2000)}\n"
        description += f"**Model:** {video_params.model}\n"
        description += f"**Size:** {video_params.size}\n"
        description += f"**Duration:** {video_params.seconds} seconds\n"

        embed = Embed(title="Video Generation", description=description, color=Colour.blue())
        embeds = [embed]
        vid_seconds = int(video_params.seconds)
        vid_cost = calculate_video_cost(model, vid_seconds)
        daily_cost = cog._track_daily_cost_direct(
            ctx.author.id,
            "video",
            model,
            vid_cost,
            f"seconds={vid_seconds} | size={video_params.size}",
        )
        if SHOW_COST_EMBEDS:
            append_flat_pricing_embed(
                embeds, vid_cost, daily_cost, f"{vid_seconds}s · {video_params.size}"
            )

        await send_embed_batches(
            ctx.send_followup,
            embeds=embeds,
            file=File(video_file_path),
            logger=cog.logger,
        )
        cog.logger.info("Successfully sent generated video")
    except Exception as e:
        description = format_openai_error(e)
        cog.logger.error(f"Video generation failed: {description}", exc_info=True)
        await send_embed_batches(ctx.send_followup, embed=error_embed(description), logger=cog.logger)
    finally:
        if video_file_path and video_file_path.exists():
            video_file_path.unlink(missing_ok=True)
