"""Tool: get_health_advice — wraps backend/chatbot_logic.generate_chat_response.

The chatbot's response logic was extracted from the Flask route into the
flask-free ``backend/chatbot_logic.py`` so it can be reused here (and unit
tested) without standing up the web server.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..errors import WatError
from ..paths import ensure_backend_on_path
from ..registry import Tool, register


class AdviceInput(BaseModel):
    message: str = Field(min_length=1)


class AdviceOutput(BaseModel):
    response: str


@register
class GetHealthAdvice(Tool):
    name = "get_health_advice"
    Input = AdviceInput
    Output = AdviceOutput
    kind = "cli"

    def run(self, inp: AdviceInput) -> AdviceOutput:
        ensure_backend_on_path()
        try:
            from chatbot_logic import generate_chat_response
        except ImportError as exc:
            raise WatError("chatbot_logic unavailable", category="dependency", cause=exc)
        return AdviceOutput(response=generate_chat_response(inp.message))
