import os
from typing import Any

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult


class MockArchaeologyChatModel(BaseChatModel):
    """
    Deterministic offline fallback LLM.
    Allows all unit tests and local runs to run fast and reliably with 0 network or API key dependencies.
    """

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        prompt_text = "\n".join(str(m.content) for m in messages)

        # Check if active replacement was detected in the prompt
        if "Replacement Matches:" in prompt_text and "None detected" not in prompt_text:
            content = (
                "Inferred purpose: Legacy implementation superseded by modern counterpart. "
                "The functionality has been relocated and this dead symbol is safe for deletion."
            )
        else:
            content = (
                "Inferred purpose: Standalone historical utility with no detected active callers. "
                "The code appears abandoned and is safe for deletion."
            )

        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    @property
    def _llm_type(self) -> str:
        return "mock-archaeology"


def get_llm_client() -> BaseChatModel:
    """
    Returns an active LangChain ChatModel:
    - If OPENAI_API_KEY is configured in .env -> uses ChatOpenAI
    - If GOOGLE_API_KEY or GEMINI_API_KEY is configured in .env -> uses ChatGoogleGenerativeAI
    - Otherwise -> gracefully uses the deterministic offline archaeology model.
    """
    if os.getenv("OPENAI_API_KEY"):
        try:
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(model="gpt-4o-mini", temperature=0)
        except ImportError:
            pass

    if os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY"):
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            api_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
            return ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=api_key,
                temperature=0,
            )
        except ImportError:
            pass

    return MockArchaeologyChatModel()