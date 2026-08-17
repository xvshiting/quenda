"""Provider usage normalization has one cross-protocol accounting meaning."""

from types import SimpleNamespace

from quenda.providers.usage import normalize_anthropic_usage, normalize_openai_usage


def test_openai_cached_tokens_are_a_subset_of_total_input() -> None:
    usage = normalize_openai_usage(SimpleNamespace(
        prompt_tokens=100,
        completion_tokens=20,
        prompt_tokens_details=SimpleNamespace(cached_tokens=80),
        completion_tokens_details=SimpleNamespace(reasoning_tokens=5),
    ))

    assert usage.input_tokens == 100
    assert usage.cached_input_tokens == 80
    assert usage.cache_creation_input_tokens is None
    assert usage.output_tokens == 20
    assert usage.reasoning_tokens == 5


def test_anthropic_disjoint_input_counters_are_normalized_to_total() -> None:
    usage = normalize_anthropic_usage(SimpleNamespace(
        input_tokens=20,
        cache_read_input_tokens=70,
        cache_creation_input_tokens=10,
        output_tokens=15,
    ))

    assert usage.input_tokens == 100
    assert usage.cached_input_tokens == 70
    assert usage.cache_creation_input_tokens == 10
    assert usage.output_tokens == 15
