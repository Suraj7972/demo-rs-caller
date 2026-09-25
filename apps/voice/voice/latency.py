"""Per-turn latency logging: user stops speaking -> first bot audio.

Built on Pipecat's UserBotLatencyObserver, which anchors on the VAD stop (corrected for
the VAD's own stop delay, i.e. the real end of speech) and fires at BotStartedSpeakingFrame.
The breakdown shows where the time went (STT finalisation, LLM TTFB, TTS TTFB, ...).
"""

from loguru import logger
from pipecat.observers.user_bot_latency_observer import LatencyBreakdown, UserBotLatencyObserver

TARGET_MS = 1000  # CLAUDE.md: bot starts speaking < 1 s after the user stops


class TurnLatencyLogger:
    def __init__(self, call_label: str) -> None:
        self.call_label = call_label
        self.turns_ms: list[int] = []
        self.observer = UserBotLatencyObserver()
        self.observer.add_event_handler("on_latency_measured", self._on_latency)
        self.observer.add_event_handler("on_latency_breakdown", self._on_breakdown)
        self.observer.add_event_handler("on_first_bot_speech_latency", self._on_first_speech)

    async def _on_latency(self, _observer: UserBotLatencyObserver, latency_s: float) -> None:
        ms = round(latency_s * 1000)
        self.turns_ms.append(ms)
        flag = "OK " if ms <= TARGET_MS else "SLOW"
        logger.info(
            f"[latency] {self.call_label} turn {len(self.turns_ms)}: "
            f"user-stop -> first bot audio = {ms} ms [{flag}]"
        )

    async def _on_breakdown(self, _observer: UserBotLatencyObserver, b: LatencyBreakdown) -> None:
        parts = ", ".join(f"{m.processor} ttfb={round(m.duration_secs * 1000)}ms" for m in b.ttfb)
        if parts:
            logger.info(f"[latency] {self.call_label}   breakdown: {parts}")

    async def _on_first_speech(self, _observer: UserBotLatencyObserver, latency_s: float) -> None:
        logger.info(
            f"[latency] {self.call_label} connect -> first bot audio = {round(latency_s * 1000)} ms"
        )

    def summary(self) -> str:
        if not self.turns_ms:
            return f"[latency] {self.call_label} no measured turns"
        ordered = sorted(self.turns_ms)
        p50 = ordered[len(ordered) // 2]
        p90 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.9))]
        return (
            f"[latency] {self.call_label} turns={len(ordered)} p50={p50}ms p90={p90}ms "
            f"max={ordered[-1]}ms over_{TARGET_MS}ms={sum(t > TARGET_MS for t in ordered)}"
        )
