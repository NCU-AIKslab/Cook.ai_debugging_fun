"""
Vision Service Package

Provides image understanding using Vision LLMs:
- GPT-4 Vision (OpenAI)
- Future: Qwen2-VL, Claude Vision, etc.
"""

from .gpt4_vision import GPT4VisionEngine

__all__ = ['GPT4VisionEngine']
