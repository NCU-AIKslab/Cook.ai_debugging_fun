"""
Skill Configuration System

定義所有 skills 的能力與特性，用於動態建立 graph edges 和 refinement 流程。
"""

from pydantic import BaseModel
from typing import Literal


class SkillCapability(BaseModel):
    """定義 skill 的能力與特性"""
    name: str
    supports_refinement: bool  # 是否支持 refinement
    supports_critic: bool  # 是否需要 critic 評估
    refinement_strategy: Literal["partial", "full", "none"]
    # - "partial": 可以只改部分內容（如只改失敗的題目）
    # - "full": 必須完整重新生成（如 summary）
    # - "none": 不支持 refinement


# 所有 skills 的配置
# 新增 skill 時，在這裡添加配置即可
SKILL_CONFIGS = {
    "exam_generation_skill": SkillCapability(
        name="exam_generation",
        supports_refinement=True,
        supports_critic=True,
        refinement_strategy="partial"  # 可以只改失敗的題目
    ),
    "summarization_skill": SkillCapability(
        name="summarization",
        supports_refinement=True,
        supports_critic=True,
        refinement_strategy="full"  # 必須完整重新生成
    ),
    "general_chat_skill": SkillCapability(
        name="general_chat",
        supports_refinement=False,  # 對話不支持改進
        supports_critic=False,  # 不需要評估
        refinement_strategy="none"
    )
}
