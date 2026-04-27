import asyncio
import io
import time

from discord import ApplicationContext, Colour, Embed, File

from ...util import ResearchParameters, format_openai_error, hash_user_id, truncate_text
from .embed_delivery import send_embed_batches
from .embeds import append_sources_embed, append_thinking_embeds, error_embed
from .responses import extract_summary_text
from .tooling import extract_tool_info


async def run_research_command(
    cog,
    ctx: ApplicationContext,
    prompt: str,
    model: str,
    file_search: bool,
    code_interpreter: bool,
) -> None:
    """Run the /openai research command."""
    await ctx.defer()

    research_params = ResearchParameters(
        prompt=prompt,
        model=model,
        file_search=file_search,
        code_interpreter=code_interpreter,
    )

    try:
        selected_tool_names = ["web_search"]
        if file_search:
            selected_tool_names.append("file_search")
        if code_interpreter:
            selected_tool_names.append("code_interpreter")

        tools, tool_error = cog.resolve_selected_tools(selected_tool_names, model)
        if tool_error:
            await send_embed_batches(
                ctx.send_followup, embed=error_embed(tool_error), logger=cog.logger
            )
            return

        description = f"**Prompt:** {truncate_text(prompt, 2000)}\n"
        description += f"**Model:** {model}\n"
        description += f"**Tools:** {', '.join(selected_tool_names)}\n"
        description += "\nResearching... this may take several minutes."

        status_msg = await send_embed_batches(
            ctx.send_followup,
            embed=Embed(title="Deep Research", description=description, color=Colour.green()),
            logger=cog.logger,
        )

        api_dict = research_params.to_dict(tools)
        api_dict["safety_identifier"] = hash_user_id(ctx.author.id)
        response = await cog.openai_client.responses.create(**api_dict)

        max_wait_time = 1200
        start_time = time.time()
        poll_interval = 15
        while response.status in ("queued", "in_progress"):
            if time.time() - start_time > max_wait_time:
                raise Exception("Deep research timed out after 20 minutes.")

            await asyncio.sleep(poll_interval)
            response = await cog.openai_client.responses.retrieve(response.id)
            cog.logger.debug(
                f"Research poll: status={response.status}, elapsed={int(time.time() - start_time)}s"
            )

        if response.status == "failed":
            error = getattr(response, "error", None)
            error_msg = getattr(error, "message", None) if error else None
            raise Exception(error_msg or "Deep research failed. Please try a different prompt.")
        if response.status == "cancelled":
            raise Exception("Deep research was cancelled.")
        if response.status != "completed":
            raise Exception(f"Unexpected research status: {response.status}")

        response_text = getattr(response, "output_text", None) or None
        if not response_text:
            await status_msg.edit(
                embed=Embed(
                    title="Deep Research",
                    description="The research model did not produce any output. Please try again with a different prompt.",
                    color=Colour.orange(),
                )
            )
            return

        tool_info = extract_tool_info(response)
        elapsed = int(time.time() - start_time)
        final_description = f"**Prompt:** {truncate_text(prompt, 2000)}\n"
        final_description += f"**Model:** {model}\n"
        final_description += f"**Tools:** {', '.join(selected_tool_names)}\n"
        final_description += f"**Time:** {elapsed // 60}m {elapsed % 60}s\n"
        header_embed = Embed(
            title="Deep Research", description=final_description, color=Colour.blue()
        )

        extra_embeds = []
        append_thinking_embeds(extra_embeds, extract_summary_text(response))
        if tool_info["citations"] or tool_info["file_citations"]:
            append_sources_embed(extra_embeds, tool_info["citations"], tool_info["file_citations"])
        cog._track_and_append_cost(
            extra_embeds,
            ctx.author.id,
            model,
            response,
            tool_info,
            command="research",
        )

        await status_msg.edit(embed=header_embed)
        report_file = File(io.BytesIO(response_text.encode("utf-8")), filename="research_report.md")
        await send_embed_batches(
            ctx.send_followup,
            embeds=extra_embeds if extra_embeds else [],
            file=report_file,
            logger=cog.logger,
        )
    except Exception as e:
        description = format_openai_error(e)
        cog.logger.error(f"Deep research failed: {description}", exc_info=True)
        await send_embed_batches(ctx.send_followup, embed=error_embed(description), logger=cog.logger)
