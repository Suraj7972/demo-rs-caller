"""LLM provider interface.

The live call uses a fast, cheap model; the provider is picked by env
(LLM_LIVE_PROVIDER / LLM_LIVE_MODEL) so it can be swapped without code changes.
Pipecat is imported lazily so api/worker (which don't use Pipecat) never import it.
"""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from shared.config import Settings

if TYPE_CHECKING:
    from pipecat.services.llm_service import LLMService


class LLMProvider(ABC):
    name: str

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError(f"{self.name}: missing API key")
        self.api_key = api_key
        self.model = model

    @abstractmethod
    def pipecat_service(self, system_instruction: str, **settings: Any) -> "LLMService":
        """A streaming Pipecat LLM service for the live-call pipeline."""


class SarvamLLMProvider(LLMProvider):
    name = "sarvam"

    def pipecat_service(self, system_instruction: str, **settings: Any) -> "LLMService":
        from pipecat.services.sarvam.llm import SarvamLLMService

        return SarvamLLMService(
            api_key=self.api_key,
            settings=SarvamLLMService.Settings(
                model=self.model, system_instruction=system_instruction, **settings
            ),
        )


class OpenAILLMProvider(LLMProvider):
    name = "openai"

    def pipecat_service(self, system_instruction: str, **settings: Any) -> "LLMService":
        from pipecat.services.openai.llm import OpenAILLMService

        return OpenAILLMService(
            api_key=self.api_key,
            settings=OpenAILLMService.Settings(
                model=self.model, system_instruction=system_instruction, **settings
            ),
        )


class AnthropicLLMProvider(LLMProvider):
    name = "anthropic"

    def pipecat_service(self, system_instruction: str, **settings: Any) -> "LLMService":
        from pipecat.services.anthropic.llm import AnthropicLLMService

        return AnthropicLLMService(
            api_key=self.api_key,
            settings=AnthropicLLMService.Settings(
                model=self.model, system_instruction=system_instruction, **settings
            ),
        )


def live_llm_provider(settings: Settings) -> LLMProvider:
    """The live-call LLM configured by env."""
    keys = {
        "sarvam": settings.sarvam_api_key,
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
    }
    classes: dict[str, type[LLMProvider]] = {
        "sarvam": SarvamLLMProvider,
        "openai": OpenAILLMProvider,
        "anthropic": AnthropicLLMProvider,
    }
    provider = settings.llm_live_provider
    key = keys[provider]
    return classes[provider](key.get_secret_value() if key else "", settings.llm_live_model)
