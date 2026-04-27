import base64
import io
from typing import Any, cast

from discord import ApplicationContext, Attachment, Colour, Embed, File

from ...config.auth import SHOW_COST_EMBEDS
from ...util import calculate_image_cost, format_openai_error, truncate_text
from .attachments import download_attachment, validate_image_attachment
from .embed_delivery import send_embed_batches
from .embeds import append_flat_pricing_embed, error_embed
from .models import ImageGenerationParameters


async def run_image_command(
    cog,
    ctx: ApplicationContext,
    prompt: str,
    model: str,
    quality: str | None,
    size: str | None,
    attachment: Attachment | None,
) -> None:
    """Run the /openai image command."""
    await ctx.defer()

    is_editing = attachment is not None
    mode = "Image Editing" if is_editing else "Image Generation"
    validation_error = validate_image_attachment(attachment)
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
    )
    cog.logger.info(f"{mode} with model {model}")

    image_file_path = None
    try:
        if is_editing:
            image_file_path = await download_attachment(attachment.url, attachment.filename)
            with open(image_file_path, "rb") as image_file:
                response = await cog.openai_client.images.edit(
                    image=image_file,
                    prompt=prompt,
                    model=model,
                    n=1,
                    quality=cast(Any, quality),
                    size=cast(Any, size),
                )
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

        description = (
            f"**Prompt:** {truncate_text(image_params.prompt, 2000)}\n"
            f"**Model:** {image_params.model}\n"
            f"**Mode:** {mode}\n"
            f"**Quality:** {image_params.quality}\n"
            f"**Size:** {image_params.size}\n"
        )

        embed = Embed(title=mode, description=description, color=Colour.blue())
        embed.set_image(url=f"attachment://{image_files[0].filename}")

        embeds = [embed]
        effective_quality = quality or "auto"
        effective_size = size or "auto"
        image_cost = calculate_image_cost(
            model, effective_quality, effective_size, len(image_files)
        )
        daily_cost = cog._track_daily_cost_direct(
            ctx.author.id,
            "image",
            model,
            image_cost,
            f"mode={mode.lower()} | quality={effective_quality} | size={effective_size} | n={len(image_files)}",
        )
        if SHOW_COST_EMBEDS:
            append_flat_pricing_embed(
                embeds,
                image_cost,
                daily_cost,
                f"{mode.lower()} · {effective_quality} · {effective_size} · {len(image_files)} image(s)",
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
        await send_embed_batches(ctx.send_followup, embed=error_embed(description), logger=cog.logger)
    finally:
        if image_file_path and image_file_path.exists():
            image_file_path.unlink(missing_ok=True)
