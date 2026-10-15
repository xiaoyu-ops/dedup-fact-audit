"""Minimal model-call interface. Set OPENAI_API_KEY or ANTHROPIC_API_KEY; the model name selects the provider."""
import os
from .prompts import parse_json


def call_model(prompt, model, timeout=900):
    """Send one prompt and return the parsed JSON object from the response."""
    if model.startswith(("gpt", "o")):
        from openai import OpenAI
        client = OpenAI(timeout=timeout)
        resp = client.chat.completions.create(model=model, messages=[{"role": "user", "content": prompt}])
        text = resp.choices[0].message.content
    elif model.startswith("claude"):
        import anthropic
        client = anthropic.Anthropic(timeout=timeout)
        resp = client.messages.create(model=model, max_tokens=16000, messages=[{"role": "user", "content": prompt}])
        text = "".join(b.text for b in resp.content if b.type == "text")
    else:
        raise ValueError(f"unknown model provider for {model!r}")
    return parse_json(text)
