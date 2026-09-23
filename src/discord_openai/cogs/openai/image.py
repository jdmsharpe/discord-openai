import asyncio
import base64
import io
from typing import Any

from discord import ApplicationContext, Attachment, Colour, Embed, File

from ...config.auth import SHOW_COST_EMBEDS
from ...cost_line import count_label
from ...util import (
    calculate_image_cost,
    calculate_image_cost_from_usage,
    format_openai_error,
    image_quality_error,
    truncate_text,
)
from .attachments import download_attachment, validate_image_attachment
from .embed_delivery import send_embed_batches
from .embeds import append_flat_pricing_embed, error_embed
from .models import ImageGenerationParameters


def _served_value(served: Any, requested: str | None) -> str:
    """The quality/size the API reports it served, else what was requested."""
    if isinstance(served, str) and served:
        return served
    return requested or "auto"


def _describe_served(requested: str | None, served: str) -> str:
    """Show the served value, marking it when the request left the choice to the API."""
    if requested in (None, "auto") and served != "auto":
        return f"{served} (auto)"
    return served


async def run_image_command(
    cog,
    ctx: ApplicationContext,
    prompt: str,
    model: str,
    quality: str | None,
    size: str | None,
    attachment: Attachment | None,
    background: str | None = "auto",
) -> None:
    """Run the /openai-media image command."""
    await ctx.defer()

    is_editing = attachment is not None
    mode = "Image Editing" if is_editing else "Image Generation"
    validation_error = validate_image_attachment(attachment) or image_quality_error(model, quality)
    if validation_error:
        await send_embed_batches(
            ctx.send_followup, embed=error_embed(validation_error), logger=cog.logger
        )
        return

    image_params = ImageGenerationParameters(
        prompt=prompt,
        model=model,
        quality=quality,
        size=size,
        background=background,
    )
    cog.logger.info(f"{mode} with model {model}")

    image_file_path = None
    try:
        if is_editing:
            image_file_path = await download_attachment(attachment.url, attachment.filename)
            image_bytes = await asyncio.to_thread(image_file_path.read_bytes)
            edit_kwargs: dict[str, Any] = {
                "image": (attachment.filename, image_bytes),
                "prompt": prompt,
                "model": model,
                "n": 1,
                "quality": quality,
                "size": size,
            }
            if image_params.background is not None:
                edit_kwargs["background"] = image_params.background
            if image_params.output_format is not None:
                edit_kwargs["output_format"] = image_params.output_format
            response = await cog.openai_client.images.edit(**edit_kwargs)
        else:
            response = await cog.openai_client.images.generate(**image_params.to_dict())

        image_files = []
        for idx, data_item in enumerate(response.data or []):
            if hasattr(data_item, "b64_json") and data_item.b64_json:
                image_bytes = base64.b64decode(data_item.b64_json)
                data = io.BytesIO(image_bytes)
                image_files.append(File(data, f"image{idx}.png"))

        if not image_files:
            raise Exception("No images were generated.")

        # The response echoes the quality and size the API served; an `auto`
        # request is resolved server-side, often to `low` at a non-standard size.
        effective_quality = _served_value(getattr(response, "quality", None), quality)
        effective_size = _served_value(getattr(response, "size", None), size)

        description = (
            f"**Prompt:** {truncate_text(image_params.prompt, 2000)}\n"
            f"**Model:** {image_params.model}\n"
            f"**Mode:** {mode}\n"
            f"**Quality:** {_describe_served(image_params.quality, effective_quality)}\n"
            f"**Size:** {_describe_served(image_params.size, effective_size)}\n"
        )
        if image_params.background and image_params.background != "auto":
            description += f"**Background:** {image_params.background}\n"

        embed = Embed(title=mode, description=description, color=Colour.blue())
        embed.set_image(url=f"attachment://{image_files[0].filename}")

        embeds = [embed]
        # Bill from the token usage the response reports (exact, covers `auto`
        # and non-standard sizes); the per-image table is the fallback.
        usage = getattr(response, "usage", None)
        usage_cost = calculate_image_cost_from_usage(model, usage)
        image_cost = (
            usage_cost
            if usage_cost is not None
            else calculate_image_cost(model, effective_quality, effective_size, len(image_files))
        )
        daily_cost = cog._track_daily_cost_direct(
            ctx.author.id,
            "image",
            model,
            image_cost,
            f"mode={mode.lower()} | quality={effective_quality} | size={effective_size}"
            f" | background={image_params.background or 'auto'} | n={len(image_files)}",
        )
        if SHOW_COST_EMBEDS:
            image_label = "edited image" if is_editing else "image"
            append_flat_pricing_embed(
                embeds,
                image_cost,
                daily_cost,
                [count_label(len(image_files), image_label), effective_quality, effective_size],
                input_tokens=getattr(usage, "input_tokens", None)
                if usage_cost is not None
                else None,
                output_tokens=(
                    getattr(usage, "output_tokens", None) if usage_cost is not None else None
                ),
            )

        await send_embed_batches(
            ctx.send_followup,
            embeds=embeds,
            files=image_files,
            logger=cog.logger,
        )
        cog.logger.info(
            f"Successfully {mode.lower().replace(' ', '-')}d and sent {len(image_files)} image(s)"
        )
    except Exception as e:
        description = format_openai_error(e)
        cog.logger.error(f"{mode} failed: {description}", exc_info=True)
        await send_embed_batches(
            ctx.send_followup, embed=error_embed(description), logger=cog.logger
        )
    finally:
        if image_file_path and image_file_path.exists():
            image_file_path.unlink(missing_ok=True)
