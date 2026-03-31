import logging
from typing import Any

from discord import (
    ApplicationContext,
    Attachment,
    Embed,
)
from discord.commands import OptionChoice, SlashCommandGroup, option
from discord.ext import commands

from ...config.auth import GUILD_IDS
from .chat import (
    handle_check_permissions,
    handle_on_message,
    run_chat_command,
)
from .chat import (
    handle_new_message_in_conversation as handle_conversation_message,
)
from .chat import (
    keep_typing as keep_typing_loop,
)
from .client import build_openai_client
from .image import run_image_command
from .research import run_research_command
from .speech import run_stt_command, run_tts_command
from .state import (
    cleanup_conversation,
    create_button_view,
    stop_conversation,
    strip_previous_view,
    track_and_append_cost,
    track_daily_cost,
    track_daily_cost_direct,
)
from .state import (
    handle_tools_changed as apply_tool_changes,
)
from .tooling import ToolInfo, resolve_selected_tools
from .video import run_video_command


class OpenAICog(commands.Cog):
    openai = SlashCommandGroup("openai", "OpenAI commands", guild_ids=GUILD_IDS)

    def __init__(self, bot):
        """Initialize the OpenAI cog."""
        self.logger = logging.getLogger(__name__)
        self.bot = bot
        self.openai_client = build_openai_client()

        self.conversation_histories = {}
        self.views = {}
        self.last_view_messages = {}
        self.daily_costs = {}

    async def _strip_previous_view(self, user) -> None:
        await strip_previous_view(self, user)

    async def _cleanup_conversation(self, user) -> None:
        await cleanup_conversation(self, user)

    async def _stop_conversation(self, conversation_id: int, user) -> None:
        await stop_conversation(self, conversation_id, user)

    def _create_button_view(self, user, conversation_id: int, tools=None):
        return create_button_view(self, user, conversation_id, tools)

    def _handle_tools_changed(
        self, selected_values: list[str], conversation
    ) -> tuple[set[str], str | None]:
        return apply_tool_changes(self, selected_values, conversation)

    def _track_daily_cost(
        self,
        user_id: int,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
        tool_call_counts: dict[str, int] | None = None,
        command: str = "chat",
    ) -> float:
        return track_daily_cost(
            self,
            user_id,
            model,
            input_tokens,
            output_tokens,
            cached_tokens,
            tool_call_counts,
            command,
        )

    def _track_daily_cost_direct(
        self,
        user_id: int,
        command: str,
        model: str,
        cost: float,
        details: str = "",
    ) -> float:
        return track_daily_cost_direct(self, user_id, command, model, cost, details)

    def _track_and_append_cost(
        self,
        embeds: list[Embed],
        user_id: int,
        model: str,
        response: Any,
        tool_info: ToolInfo,
        command: str = "chat",
    ) -> None:
        track_and_append_cost(self, embeds, user_id, model, response, tool_info, command)

    def resolve_selected_tools(
        self, selected_tool_names: list[str], model: str
    ) -> tuple[list[dict[str, Any]], str | None]:
        return resolve_selected_tools(selected_tool_names, model)

    async def handle_new_message_in_conversation(self, message, conversation):
        await handle_conversation_message(self, message, conversation)

    async def keep_typing(self, channel):
        await keep_typing_loop(channel)

    # Added for debugging purposes
    @commands.Cog.listener()
    async def on_ready(self):
        """
        Event listener that runs when the bot is ready.
        Logs bot details and attempts to synchronize commands.
        """
        self.logger.info(f"Logged in as {self.bot.user} (ID: {self.bot.owner_id})")
        self.logger.info(f"Attempting to sync commands for guilds: {GUILD_IDS}")
        try:
            await self.bot.sync_commands()
            self.logger.info("Commands synchronized successfully.")
        except Exception as e:
            self.logger.error(f"Error during command synchronization: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        await handle_on_message(self, message)

    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """
        Event listener that runs when an error occurs.

        Args:
            event: The name of the event that raised the error.
            *args: Variable length argument list.
            **kwargs: Arbitrary keyword arguments.
        """
        self.logger.error(f"Error in event {event}: {args} {kwargs}", exc_info=True)

    @openai.command(
        name="check_permissions",
        description="Check if bot has necessary permissions in this channel",
    )
    async def check_permissions(self, ctx: ApplicationContext):
        await handle_check_permissions(self, ctx)

    @openai.command(
        name="chat",
        description="Starts a conversation with a model.",
    )
    @option("prompt", description="Prompt", required=True, type=str)
    @option(
        "persona",
        description="What role you want the model to emulate. (default: You are a helpful assistant.)",
        required=False,
        type=str,
    )
    @option(
        "model",
        description="Choose from the following GPT models. (default: GPT-5.4)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT-5.4 Pro", value="gpt-5.4-pro"),
            OptionChoice(name="GPT-5.4", value="gpt-5.4"),
            OptionChoice(name="GPT-5.4 Mini", value="gpt-5.4-mini"),
            OptionChoice(name="GPT-5.4 Nano", value="gpt-5.4-nano"),
            OptionChoice(name="GPT-5.3", value="gpt-5.3-chat-latest"),
            OptionChoice(name="GPT-5.2 Pro", value="gpt-5.2-pro"),
            OptionChoice(name="GPT-5.2", value="gpt-5.2"),
            OptionChoice(name="GPT-5.1", value="gpt-5.1"),
            OptionChoice(name="GPT-5 Pro", value="gpt-5-pro"),
            OptionChoice(name="GPT-5", value="gpt-5"),
            OptionChoice(name="GPT-5 Mini", value="gpt-5-mini"),
            OptionChoice(name="GPT-5 Nano", value="gpt-5-nano"),
            OptionChoice(name="GPT-4.1", value="gpt-4.1"),
            OptionChoice(name="GPT-4.1 Mini", value="gpt-4.1-mini"),
            OptionChoice(name="GPT-4.1 Nano", value="gpt-4.1-nano"),
            OptionChoice(name="o4 Mini", value="o4-mini"),
            OptionChoice(name="o3 Pro", value="o3-pro"),
            OptionChoice(name="o3", value="o3"),
            OptionChoice(name="o3 Mini", value="o3-mini"),
            OptionChoice(name="o1 Pro", value="o1-pro"),
            OptionChoice(name="o1", value="o1"),
            OptionChoice(name="GPT-4o", value="gpt-4o"),
            OptionChoice(name="GPT-4o Mini", value="gpt-4o-mini"),
            OptionChoice(name="GPT-4", value="gpt-4"),
            OptionChoice(name="GPT-4 Turbo", value="gpt-4-turbo"),
        ],
    )
    @option(
        "attachment",
        description="Attach an image, PDF, document, spreadsheet, or code file. (default: not set)",
        required=False,
        type=Attachment,
    )
    @option(
        "frequency_penalty",
        description="(Advanced) Controls how much the model should repeat itself. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "presence_penalty",
        description="(Advanced) Controls how much the model should talk about the prompt. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "temperature",
        description="(Advanced) Controls the randomness of the model. Set this or top_p, but not both. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "top_p",
        description="(Advanced) Nucleus sampling. Set this or temperature, but not both. (default: not set)",
        required=False,
        type=float,
    )
    @option(
        "reasoning_effort",
        description="(Advanced) Reasoning depth. none=fastest, xhigh=deepest. (default: not set)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="None (fastest, no reasoning)", value="none"),
            OptionChoice(name="Minimal", value="minimal"),
            OptionChoice(name="Low", value="low"),
            OptionChoice(name="Medium", value="medium"),
            OptionChoice(name="High", value="high"),
            OptionChoice(name="Extra High", value="xhigh"),
        ],
    )
    @option(
        "verbosity",
        description="(Advanced) Controls response length. low=concise, high=detailed. (default: medium)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Low (concise)", value="low"),
            OptionChoice(name="Medium (default)", value="medium"),
            OptionChoice(name="High (detailed)", value="high"),
        ],
    )
    @option(
        "web_search",
        description="Enable web search to find current information. (default: false)",
        required=False,
        type=bool,
    )
    @option(
        "code_interpreter",
        description="Enable code interpreter to run Python code. (default: false)",
        required=False,
        type=bool,
    )
    @option(
        "file_search",
        description="Enable file search over configured vector stores. (default: false)",
        required=False,
        type=bool,
    )
    @option(
        "shell",
        description="Enable hosted shell command execution (GPT-5 models). (default: false)",
        required=False,
        type=bool,
    )
    async def chat(
        self,
        ctx: ApplicationContext,
        prompt: str,
        persona: str = "You are a helpful assistant.",
        model: str = "gpt-5.4",
        attachment: Attachment | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        temperature: float | None = None,
        top_p: float | None = None,
        reasoning_effort: str | None = None,
        verbosity: str | None = None,
        web_search: bool = False,
        code_interpreter: bool = False,
        file_search: bool = False,
        shell: bool = False,
    ):
        await run_chat_command(
            self,
            ctx,
            prompt,
            persona,
            model,
            attachment,
            frequency_penalty,
            presence_penalty,
            temperature,
            top_p,
            reasoning_effort,
            verbosity,
            web_search,
            code_interpreter,
            file_search,
            shell,
        )

    @openai.command(
        name="image",
        description="Generates or edits an image from a prompt.",
    )
    @option("prompt", description="Prompt", required=True, type=str)
    @option(
        "model",
        description="Choose from the following image generation models. (default: GPT Image 1.5)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT Image 1.5", value="gpt-image-1.5"),
            OptionChoice(name="GPT Image 1", value="gpt-image-1"),
            OptionChoice(name="GPT Image 1 Mini", value="gpt-image-1-mini"),
        ],
    )
    @option(
        "quality",
        description="Image quality. (default: auto)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Auto", value="auto"),
            OptionChoice(name="Low", value="low"),
            OptionChoice(name="Medium", value="medium"),
            OptionChoice(name="High", value="high"),
        ],
    )
    @option(
        "size",
        description="Size of the image. (default: auto)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Auto", value="auto"),
            OptionChoice(name="1024x1024 (square)", value="1024x1024"),
            OptionChoice(name="1024x1536 (portrait)", value="1024x1536"),
            OptionChoice(name="1536x1024 (landscape)", value="1536x1024"),
        ],
    )
    @option(
        "attachment",
        description="Image to edit (PNG, JPEG, GIF, WebP). Omit to generate a new image.",
        required=False,
        type=Attachment,
    )
    async def image(
        self,
        ctx: ApplicationContext,
        prompt: str,
        model: str = "gpt-image-1.5",
        quality: str | None = "auto",
        size: str | None = "auto",
        attachment: Attachment | None = None,
    ):
        await run_image_command(self, ctx, prompt, model, quality, size, attachment)

    @openai.command(
        name="tts",
        description="Generates lifelike audio from the input text.",
    )
    @option(
        "input",
        description="Text to convert to speech. (max length 4096 characters)",
        required=True,
        type=str,
    )
    @option(
        "model",
        description="Choose from the following TTS models. (default: GPT-4o Mini TTS)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT-4o Mini TTS", value="gpt-4o-mini-tts"),
            OptionChoice(name="TTS-1", value="tts-1"),
            OptionChoice(name="TTS-1 HD", value="tts-1-hd"),
        ],
    )
    @option(
        "voice",
        description="The voice to use when generating the audio. (default: Marin)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Marin (Only supported with GPT-4o Mini TTS)", value="marin"),
            OptionChoice(name="Cedar (Only supported with GPT-4o Mini TTS)", value="cedar"),
            OptionChoice(name="Alloy", value="alloy"),
            OptionChoice(name="Ash", value="ash"),
            OptionChoice(name="Ballad (Only supported with GPT-4o Mini TTS)", value="ballad"),
            OptionChoice(name="Coral", value="coral"),
            OptionChoice(name="Echo", value="echo"),
            OptionChoice(name="Fable", value="fable"),
            OptionChoice(name="Nova", value="nova"),
            OptionChoice(name="Onyx", value="onyx"),
            OptionChoice(name="Sage", value="sage"),
            OptionChoice(name="Shimmer", value="shimmer"),
            OptionChoice(name="Verse (Only supported with GPT-4o Mini TTS)", value="verse"),
        ],
    )
    @option(
        "instructions",
        description="Control the voice of your generated audio with additional instructions. (default: not set)",
        required=False,
        type=str,
    )
    @option(
        "response_format",
        description="The format of the audio file output. (default: mp3)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="MP3", value="mp3"),
            OptionChoice(name="WAV", value="wav"),
            OptionChoice(name="Opus", value="opus"),
            OptionChoice(name="AAC", value="aac"),
            OptionChoice(name="FLAC", value="flac"),
            OptionChoice(name="PCM", value="pcm"),
        ],
    )
    @option(
        "speed",
        description="Speed of the generated audio. (default: 1.0)",
        required=False,
        type=float,
    )
    async def tts(
        self,
        ctx: ApplicationContext,
        input: str,
        model: str = "gpt-4o-mini-tts",
        voice: str = "marin",
        instructions: str = "",
        response_format: str = "mp3",
        speed: float = 1.0,
    ):
        await run_tts_command(self, ctx, input, model, voice, instructions, response_format, speed)

    @openai.command(
        name="stt",
        description="Generates text from the input audio.",
    )
    @option(
        "attachment",
        description="Attachment audio file. Max size 25 MB. Supported types: mp3, mp4, mpeg, mpga, m4a, wav, and webm.",
        required=True,
        type=Attachment,
    )
    @option(
        "model",
        description="Model to use for speech-to-text conversion. (default: GPT-4o Transcribe)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="GPT-4o Transcribe", value="gpt-4o-transcribe"),
            OptionChoice(name="GPT-4o Mini Transcribe", value="gpt-4o-mini-transcribe"),
            OptionChoice(name="GPT-4o Transcribe Diarize", value="gpt-4o-transcribe-diarize"),
            OptionChoice(name="Whisper", value="whisper-1"),
        ],
    )
    @option(
        "action",
        description="Action to perform. (default: Transcription)",
        required=False,
        type=str,
        choices=[
            OptionChoice(
                name="Transcription",
                value="transcription",
            ),
            OptionChoice(
                name="Translation (into English)",
                value="translation",
            ),
        ],
    )
    async def stt(
        self,
        ctx: ApplicationContext,
        attachment: Attachment,
        model: str = "gpt-4o-transcribe",
        action: str = "transcription",
    ):
        await run_stt_command(self, ctx, attachment, model, action)

    @openai.command(
        name="video",
        description="Generates a video based on a prompt using Sora.",
    )
    @option(
        "prompt",
        description="Prompt for video generation (describe shot type, subject, action, setting, lighting).",
        required=True,
        type=str,
    )
    @option(
        "model",
        description="Choose Sora model for video generation. (default: Sora 2)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Sora 2 (Fast)", value="sora-2"),
            OptionChoice(name="Sora 2 Pro (High Quality)", value="sora-2-pro"),
        ],
    )
    @option(
        "size",
        description="Resolution of the generated video. (default: 1280x720)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="Landscape (1280x720)", value="1280x720"),
            OptionChoice(name="Portrait (720x1280)", value="720x1280"),
            OptionChoice(name="Wide Landscape (1792x1024)", value="1792x1024"),
            OptionChoice(name="Tall Portrait (1024x1792)", value="1024x1792"),
            OptionChoice(name="1080p Landscape (1920x1080, Pro only)", value="1920x1080"),
            OptionChoice(name="1080p Portrait (1080x1920, Pro only)", value="1080x1920"),
        ],
    )
    @option(
        "seconds",
        description="Duration of the video in seconds. (default: 8)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="4 seconds", value="4"),
            OptionChoice(name="8 seconds", value="8"),
            OptionChoice(name="12 seconds", value="12"),
            OptionChoice(name="16 seconds", value="16"),
            OptionChoice(name="20 seconds", value="20"),
        ],
    )
    async def video(
        self,
        ctx: ApplicationContext,
        prompt: str,
        model: str = "sora-2",
        size: str = "1280x720",
        seconds: str = "8",
    ):
        await run_video_command(self, ctx, prompt, model, size, seconds)

    # ------------------------------------------------------------------
    # /openai research — Deep Research via background Responses API
    # ------------------------------------------------------------------

    @openai.command(
        name="research",
        description="Run a deep research task that searches, reads, and synthesizes a detailed report.",
    )
    @option(
        "prompt",
        description="Research question or topic to investigate.",
        required=True,
        type=str,
    )
    @option(
        "model",
        description="Choose the deep research model. (default: o3 Deep Research)",
        required=False,
        type=str,
        choices=[
            OptionChoice(name="o3 Deep Research", value="o3-deep-research"),
            OptionChoice(name="o4 Mini Deep Research", value="o4-mini-deep-research"),
        ],
    )
    @option(
        "file_search",
        description="Also search your uploaded document stores (File Search / RAG). (default: false)",
        required=False,
        type=bool,
    )
    @option(
        "code_interpreter",
        description="Allow the model to write and run code for analysis. (default: false)",
        required=False,
        type=bool,
    )
    async def research(
        self,
        ctx: ApplicationContext,
        prompt: str,
        model: str = "o3-deep-research",
        file_search: bool = False,
        code_interpreter: bool = False,
    ):
        await run_research_command(self, ctx, prompt, model, file_search, code_interpreter)
