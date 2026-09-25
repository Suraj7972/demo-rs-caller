"""Builds the real pipeline (Sarvam STT/TTS/LLM, Silero VAD, Plivo serializer) offline.

Catches constructor/settings mismatches against the installed Pipecat version without
placing a call; services only open their websockets when the pipeline starts.
"""

from unittest.mock import MagicMock

import pytest

from shared.db.enums import LanguageCode
from voice.bot import CallSession, build_pipeline


@pytest.mark.parametrize("lang", list(LanguageCode))
def test_pipeline_builds_for_each_language(settings, lang):
    session = CallSession(
        call_id="c0ffee00-0000-4000-8000-000000000001",
        stream_id="stream-1",
        language=lang,
        mode="test",
        label="call=test",
    )
    bot = build_pipeline(MagicMock(), session, settings)
    names = [type(p).__name__ for p in bot.pipeline.processors]
    assert names == [
        "PipelineSource",
        "FastAPIWebsocketInputTransport",  # Plivo serializer decodes µ-law here
        "SarvamSTTService",
        "LLMUserAggregator",  # Silero VAD + turn detection + barge-in
        "SarvamLLMService",
        "SarvamTTSService",
        "FastAPIWebsocketOutputTransport",
        "LLMAssistantAggregator",
        "PipelineSink",
    ]
