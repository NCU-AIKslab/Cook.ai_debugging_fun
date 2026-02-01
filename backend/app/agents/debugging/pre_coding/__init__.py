# Pre-Coding Logic Module
# This module contains the chatbot-based pre-coding logic for student guidance.

from .manager import PreCodingManager
from .agents import UnderstandingAgent, DecompositionAgent

# Re-export legacy functions for backward compatibility during transition
from .legacy import (
    get_student_precoding_state,
    process_precoding_submission,
    sanitize_question_data
)
