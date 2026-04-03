from discord.commands import OptionChoice

CHAT_MODEL_CHOICES = [
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
]

REASONING_EFFORT_CHOICES = [
    OptionChoice(name="None (fastest, no reasoning)", value="none"),
    OptionChoice(name="Minimal", value="minimal"),
    OptionChoice(name="Low", value="low"),
    OptionChoice(name="Medium", value="medium"),
    OptionChoice(name="High", value="high"),
    OptionChoice(name="Extra High", value="xhigh"),
]

VERBOSITY_CHOICES = [
    OptionChoice(name="Low (concise)", value="low"),
    OptionChoice(name="Medium (default)", value="medium"),
    OptionChoice(name="High (detailed)", value="high"),
]

IMAGE_MODEL_CHOICES = [
    OptionChoice(name="GPT Image 1.5", value="gpt-image-1.5"),
    OptionChoice(name="GPT Image 1", value="gpt-image-1"),
    OptionChoice(name="GPT Image 1 Mini", value="gpt-image-1-mini"),
]

IMAGE_QUALITY_CHOICES = [
    OptionChoice(name="Auto", value="auto"),
    OptionChoice(name="Low", value="low"),
    OptionChoice(name="Medium", value="medium"),
    OptionChoice(name="High", value="high"),
]

IMAGE_SIZE_CHOICES = [
    OptionChoice(name="Auto", value="auto"),
    OptionChoice(name="1024x1024 (square)", value="1024x1024"),
    OptionChoice(name="1024x1536 (portrait)", value="1024x1536"),
    OptionChoice(name="1536x1024 (landscape)", value="1536x1024"),
]

TTS_MODEL_CHOICES = [
    OptionChoice(name="GPT-4o Mini TTS", value="gpt-4o-mini-tts"),
    OptionChoice(name="TTS-1", value="tts-1"),
    OptionChoice(name="TTS-1 HD", value="tts-1-hd"),
]

TTS_VOICE_CHOICES = [
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
]

TTS_RESPONSE_FORMAT_CHOICES = [
    OptionChoice(name="MP3", value="mp3"),
    OptionChoice(name="WAV", value="wav"),
    OptionChoice(name="Opus", value="opus"),
    OptionChoice(name="AAC", value="aac"),
    OptionChoice(name="FLAC", value="flac"),
    OptionChoice(name="PCM", value="pcm"),
]

STT_MODEL_CHOICES = [
    OptionChoice(name="GPT-4o Transcribe", value="gpt-4o-transcribe"),
    OptionChoice(name="GPT-4o Mini Transcribe", value="gpt-4o-mini-transcribe"),
    OptionChoice(name="GPT-4o Transcribe Diarize", value="gpt-4o-transcribe-diarize"),
    OptionChoice(name="Whisper", value="whisper-1"),
]

STT_ACTION_CHOICES = [
    OptionChoice(name="Transcription", value="transcription"),
    OptionChoice(name="Translation (into English)", value="translation"),
]

VIDEO_MODEL_CHOICES = [
    OptionChoice(name="Sora 2 (Fast)", value="sora-2"),
    OptionChoice(name="Sora 2 Pro (High Quality)", value="sora-2-pro"),
]

VIDEO_SIZE_CHOICES = [
    OptionChoice(name="Landscape (1280x720)", value="1280x720"),
    OptionChoice(name="Portrait (720x1280)", value="720x1280"),
    OptionChoice(name="Wide Landscape (1792x1024)", value="1792x1024"),
    OptionChoice(name="Tall Portrait (1024x1792)", value="1024x1792"),
    OptionChoice(name="1080p Landscape (1920x1080, Pro only)", value="1920x1080"),
    OptionChoice(name="1080p Portrait (1080x1920, Pro only)", value="1080x1920"),
]

VIDEO_SECONDS_CHOICES = [
    OptionChoice(name="4 seconds", value="4"),
    OptionChoice(name="8 seconds", value="8"),
    OptionChoice(name="12 seconds", value="12"),
    OptionChoice(name="16 seconds", value="16"),
    OptionChoice(name="20 seconds", value="20"),
]

RESEARCH_MODEL_CHOICES = [
    OptionChoice(name="o3 Deep Research", value="o3-deep-research"),
    OptionChoice(name="o4 Mini Deep Research", value="o4-mini-deep-research"),
]
