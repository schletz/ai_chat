from dataclasses import dataclass


@dataclass(frozen=True)
class LLMResult:
    """Structured result of a single LLM inference call.

    Carries the cleaned assistant text together with usage metadata that the
    frontend uses to surface how full the model context currently is.

    Attributes:
        content: The stripped assistant text returned by the model.
        total_tokens: Combined prompt and completion token count as reported
            by the underlying runtime's usage statistics. Approximates the
            number of tokens that the next inference call will carry in its
            context window.
    """

    content: str
    total_tokens: int
