"""The live-call Pipecat pipeline.

    Plivo WS -> PlivoFrameSerializer -> transport.input
      -> Sarvam STT (streaming WS)
      -> user aggregator (Silero VAD + turn detection; barge-in emits interruptions)
      -> LLM (LLMProvider, default Sarvam)
      -> Sarvam Bulbul TTS (streaming WS, 8 kHz)
      -> transport.output -> Plivo
      -> assistant aggregator

On Pipecat 1.x the Silero VAD sits in the user aggregator (it broadcasts VAD frames
upstream, so STT still flushes on end-of-speech). Interruptions are on by default:
the VAD/transcription turn-start strategies emit an interruption that clears queued
bot audio, and the Plivo serializer turns that into a `clearAudio` event.

API shapes checked against pipecat-ai 1.11 source and the official
pipecat-examples/plivo-chatbot/outbound example.
"""

import asyncio
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket
from loguru import logger
from pipecat.audio.vad.silero import SileroVADAnalyzer
from pipecat.frames.frames import EndFrame, TTSSpeakFrame
from pipecat.observers.loggers.transcription_log_observer import TranscriptionLogObserver
from pipecat.pipeline.pipeline import Pipeline
from pipecat.pipeline.worker import PipelineParams, PipelineWorker
from pipecat.processors.aggregators.llm_context import LLMContext
from pipecat.processors.aggregators.llm_response_universal import (
    LLMContextAggregatorPair,
    LLMUserAggregatorParams,
)
from pipecat.serializers.plivo import PlivoFrameSerializer
from pipecat.services.sarvam.stt import SarvamSTTService
from pipecat.services.sarvam.tts import SarvamTTSService
from pipecat.transcriptions.language import Language
from pipecat.transports.websocket.fastapi import (
    FastAPIWebsocketParams,
    FastAPIWebsocketTransport,
)
from pipecat.workers.runner import WorkerRunner

from shared.config import Settings
from shared.db.enums import LanguageCode
from shared.providers.llm import live_llm_provider
from voice.latency import TurnLatencyLogger
from voice.prompts import TEST_GREETINGS, test_system_prompt

PLIVO_SAMPLE_RATE = 8000  # µ-law 8 kHz on the wire (see stream_xml)
STT_SAMPLE_RATE = 16000  # SarvamSTTService's default input rate; serializer upsamples

_PIPECAT_LANG = {
    LanguageCode.HI: Language.HI_IN,
    LanguageCode.MR: Language.MR_IN,
    LanguageCode.EN: Language.EN_IN,
}

_STILL_THERE = {
    LanguageCode.HI: "क्या आप मुझे सुन पा रहे हैं?",
    LanguageCode.MR: "तुम्हाला माझा आवाज ऐकू येतोय का?",
    LanguageCode.EN: "Are you still there?",
}
_GOODBYE = {
    LanguageCode.HI: "ठीक है, बात करने के लिए धन्यवाद। नमस्ते!",
    LanguageCode.MR: "ठीक आहे, बोलल्याबद्दल धन्यवाद. नमस्कार!",
    LanguageCode.EN: "Alright, thank you for your time. Goodbye!",
}


@dataclass(frozen=True)
class CallSession:
    call_id: str  # Plivo CallUUID
    stream_id: str
    language: LanguageCode
    mode: str  # "test" for the smoke-test CLI; campaign calls come later
    label: str  # log-safe identifier (no phone numbers)


@dataclass
class BotPipeline:
    pipeline: Pipeline
    worker: PipelineWorker
    transport: FastAPIWebsocketTransport
    user_aggregator: Any
    latency: TurnLatencyLogger


def build_pipeline(websocket: WebSocket, session: CallSession, settings: Settings) -> BotPipeline:
    """Construct every service and the pipeline. No network I/O happens here."""
    if not settings.sarvam_api_key:
        raise RuntimeError("SARVAM_API_KEY is not set")
    if not settings.plivo_auth_id or not settings.plivo_auth_token:
        raise RuntimeError("PLIVO_AUTH_ID / PLIVO_AUTH_TOKEN are not set")
    sarvam_key = settings.sarvam_api_key.get_secret_value()
    lang = session.language

    serializer = PlivoFrameSerializer(
        stream_id=session.stream_id,
        call_id=session.call_id,
        auth_id=settings.plivo_auth_id,
        auth_token=settings.plivo_auth_token.get_secret_value(),
        params=PlivoFrameSerializer.InputParams(plivo_sample_rate=PLIVO_SAMPLE_RATE),
    )
    transport = FastAPIWebsocketTransport(
        websocket=websocket,
        params=FastAPIWebsocketParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            add_wav_header=False,
            serializer=serializer,
        ),
    )

    stt = SarvamSTTService(
        api_key=sarvam_key,
        sample_rate=STT_SAMPLE_RATE,
        settings=SarvamSTTService.Settings(
            model=settings.sarvam_stt_model, language=_PIPECAT_LANG[lang]
        ),
    )
    tts = SarvamTTSService(
        api_key=sarvam_key,
        sample_rate=PLIVO_SAMPLE_RATE,  # ask Bulbul for 8 kHz directly: no resample on the hot path
        settings=SarvamTTSService.Settings(
            model=settings.sarvam_tts_model,
            voice=settings.sarvam_tts_speaker,
            language=_PIPECAT_LANG[lang],
        ),
    )
    llm = live_llm_provider(settings).pipecat_service(
        system_instruction=test_system_prompt(lang), temperature=0.6, max_tokens=150
    )

    context = LLMContext()
    user_aggregator, assistant_aggregator = LLMContextAggregatorPair(
        context,
        user_params=LLMUserAggregatorParams(
            vad_analyzer=SileroVADAnalyzer(),
            user_idle_timeout=settings.silence_timeout_s,
        ),
    )

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    latency = TurnLatencyLogger(session.label)
    observers = [latency.observer]
    if session.mode == "test":
        observers.append(TranscriptionLogObserver())  # dev only: prints what the caller said

    worker = PipelineWorker(
        pipeline,
        params=PipelineParams(
            audio_in_sample_rate=STT_SAMPLE_RATE,
            audio_out_sample_rate=PLIVO_SAMPLE_RATE,
            enable_metrics=True,  # per-service TTFB for the latency breakdown
            enable_usage_metrics=True,
        ),
        observers=observers,
        enable_rtvi=False,  # RTVI is for web clients; nothing to talk to on a phone line
    )
    return BotPipeline(pipeline, worker, transport, user_aggregator, latency)


async def run_bot(websocket: WebSocket, session: CallSession, settings: Settings) -> None:
    bot = build_pipeline(websocket, session, settings)
    worker, transport, user_aggregator, latency = (
        bot.worker,
        bot.transport,
        bot.user_aggregator,
        bot.latency,
    )
    lang = session.language
    runner = WorkerRunner(handle_sigint=False)
    await runner.add_workers(worker)

    ending = asyncio.Event()

    async def say_goodbye_and_end(reason: str) -> None:
        if ending.is_set():
            return
        ending.set()
        logger.info(f"{session.label}: ending call ({reason})")
        # EndFrame lets queued audio finish; the serializer then hangs up via Plivo's API.
        await worker.queue_frames([TTSSpeakFrame(_GOODBYE[lang]), EndFrame()])

    idle_nudged = False

    @user_aggregator.event_handler("on_user_turn_idle")
    async def on_user_turn_idle(_aggregator) -> None:
        nonlocal idle_nudged
        if not idle_nudged:
            idle_nudged = True
            await worker.queue_frame(TTSSpeakFrame(_STILL_THERE[lang]))
        else:
            await say_goodbye_and_end(f"no speech for {settings.silence_timeout_s}s twice")

    @user_aggregator.event_handler("on_user_turn_started")
    async def on_user_turn_started(_aggregator, *_args) -> None:
        nonlocal idle_nudged
        idle_nudged = False

    @transport.event_handler("on_client_connected")
    async def on_client_connected(_transport, _client) -> None:
        logger.info(f"{session.label}: media stream connected, greeting")
        # Verbatim greeting: the AI disclosure must be the first thing the caller hears.
        await worker.queue_frame(TTSSpeakFrame(TEST_GREETINGS[lang]))

    @transport.event_handler("on_client_disconnected")
    async def on_client_disconnected(_transport, _client) -> None:
        logger.info(f"{session.label}: media stream disconnected")
        await runner.cancel()

    async def hard_limit() -> None:
        await asyncio.sleep(settings.max_call_duration_s)
        await say_goodbye_and_end(f"max duration {settings.max_call_duration_s}s")

    limiter = asyncio.create_task(hard_limit())
    try:
        await runner.run()
    finally:
        limiter.cancel()
        logger.info(latency.summary())
