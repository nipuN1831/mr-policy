from typing import Any, Protocol

DEFAULT_MODEL = "gemini-3.8-flash"


class LLM(Protocol):
    def generate_json(self, system: str, prompt: str, schema: dict[str, Any] | None = None) -> str: ...


class GeminiLLM:
    def __init__(self, model: str = DEFAULT_MODEL, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self._client = None

    def _get_client(self):
        if self._client is None:
            from google import genai

            self._client = genai.Client()
        return self._client

    def generate_json(self, system: str, prompt: str, schema: dict[str, Any] | None = None) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            response_mime_type="application/json",
            response_json_schema=schema,
        )
        response = self._get_client().models.generate_content(model=self.model, contents=prompt, config=config)
        return response.text or ""
