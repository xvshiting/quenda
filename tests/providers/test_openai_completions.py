"""Regression tests for the OpenAI-compatible transport boundary."""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from types import SimpleNamespace
from unittest.mock import patch

from quenda.kernel.types import Message, ModelResponse
from quenda.providers.api.openai_completions import OpenAICompletionsApi


def test_client_disables_hidden_sdk_retries() -> None:
    """Quenda owns retries so every retry remains observable to the user."""
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="ok", tool_calls=None),
                            finish_reason="stop",
                        )
                    ],
                    usage=None,
                )
            )
        )
    )

    with patch("openai.OpenAI", return_value=client) as constructor:
        result = OpenAICompletionsApi().invoke(
            base_url="https://example.test/v1",
            api_key="test-key",
            headers={},
            model="test-model",
            messages=[Message(role="user", content="hello")],
            tools=[],
            timeout=30,
            max_retries=0,
        )

    assert isinstance(result, ModelResponse)
    assert result.content == "ok"
    assert constructor.call_args.kwargs["max_retries"] == 0


def test_invoke_exposes_openai_cached_input_usage() -> None:
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=lambda **_: SimpleNamespace(
                    choices=[
                        SimpleNamespace(
                            message=SimpleNamespace(content="ok", tool_calls=None),
                            finish_reason="stop",
                        )
                    ],
                    usage=SimpleNamespace(
                        prompt_tokens=100,
                        completion_tokens=20,
                        prompt_tokens_details=SimpleNamespace(cached_tokens=80),
                        completion_tokens_details=SimpleNamespace(reasoning_tokens=5),
                    ),
                )
            )
        )
    )

    with patch("openai.OpenAI", return_value=client):
        result = OpenAICompletionsApi().invoke(
            base_url="https://example.test/v1",
            api_key="test-key",
            headers={},
            model="test-model",
            messages=[Message(role="user", content="hello")],
            tools=[],
            timeout=30,
            max_retries=0,
        )

    assert result.usage is not None
    assert result.usage.input_tokens == 100
    assert result.usage.cached_input_tokens == 80
    assert result.usage.reasoning_tokens == 5


def test_streaming_request_emits_final_usage_and_stop_reason() -> None:
    captured: dict[str, object] = {}
    chunks = [
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content="local-ok", reasoning_content=None, tool_calls=None
                    ),
                    finish_reason=None,
                )
            ],
            usage=None,
        ),
        SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(
                        content=None, reasoning_content=None, tool_calls=None
                    ),
                    finish_reason="stop",
                )
            ],
            usage=None,
        ),
        SimpleNamespace(
            choices=[],
            usage=SimpleNamespace(
                prompt_tokens=3,
                completion_tokens=1,
                prompt_tokens_details=None,
                completion_tokens_details=None,
            ),
        ),
    ]

    def create(**kwargs):
        captured.update(kwargs)
        return iter(chunks)

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    with patch("openai.OpenAI", return_value=client):
        result = list(
            OpenAICompletionsApi().invoke_stream(
                base_url="http://127.0.0.1:8080/v1",
                api_key="no-key",
                headers={},
                model="local-model",
                messages=[Message(role="user", content="hello")],
                tools=[],
                timeout=30,
                max_retries=0,
            )
        )

    assert captured["stream"] is True
    assert captured["stream_options"] == {"include_usage": True}
    assert result[0].content == "local-ok"
    assert result[1].stop_reason == "end_turn"
    assert result[2].usage is not None
    assert result[2].usage.input_tokens == 3


def test_llama_server_openai_chat_compatibility() -> None:
    """The existing OpenAI adapter speaks llama-server's documented /v1 route."""
    captured: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802 - stdlib handler interface
            length = int(self.headers["Content-Length"])
            captured["path"] = self.path
            captured["authorization"] = self.headers.get("Authorization")
            captured["body"] = json.loads(self.rfile.read(length))
            payload = json.dumps(
                {
                    "id": "chatcmpl-local",
                    "object": "chat.completion",
                    "created": 1,
                    "model": "qwen3.5:9b",
                    "choices": [
                        {
                            "index": 0,
                            "message": {
                                "role": "assistant",
                                "content": "local-ok",
                            },
                            "finish_reason": "stop",
                        }
                    ],
                    "usage": {
                        "prompt_tokens": 3,
                        "completion_tokens": 1,
                        "total_tokens": 4,
                    },
                }
            ).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        result = OpenAICompletionsApi().invoke(
            base_url=f"http://127.0.0.1:{server.server_port}/v1",
            api_key="no-key",
            headers={},
            model="qwen3.5:9b",
            messages=[Message(role="user", content="hello")],
            tools=[],
            timeout=5,
            max_retries=0,
        )
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert result.content == "local-ok"
    assert captured["path"] == "/v1/chat/completions"
    assert captured["authorization"] == "Bearer no-key"
    assert captured["body"] == {
        "messages": [{"role": "user", "content": "hello"}],
        "model": "qwen3.5:9b",
    }
