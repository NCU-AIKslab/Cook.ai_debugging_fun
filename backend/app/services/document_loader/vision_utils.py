"""
Vision Utilities - Pure Vision LLM for image understanding

此模組使用 GPT-4 Vision LLM 處理圖片，不再使用 OCR。
"""
import logging

logger = logging.getLogger(__name__)

def process_image_with_vision(image_bytes: bytes) -> dict:
    """
    使用 Vision LLM 處理圖片，返回描述和成本資訊
    
    Args:
        image_bytes: 圖片byte數據
    
    Returns:
        Dictionary containing:
        - description: 圖片description
        - prompt_tokens: 使用的 prompt tokens
        - completion_tokens: 使用的 completion tokens
        - cost: 估計成本 (USD)
        - model: 使用的模型
    """
    try:
        from backend.app.services.vision import GPT4VisionEngine
        import os
        
        # 初始化 Vision Engine
        model = os.getenv("VISION_MODEL", "gpt-4o-mini")
        vision_engine = GPT4VisionEngine(model=model)
        
        # 呼叫 Vision LLM
        result = vision_engine.describe_image(image_bytes)
        
        logger.info(f"✅ Vision LLM completed: {result['total_tokens']} tokens, ${result['cost']:.6f}")
        
        return result
    
    except Exception as e:
        logger.error(f"❌ Vision LLM failed: {e}")
        return {
            "description": f"[Vision Error: {e}]",
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "model": "unknown",
            "cost": 0.0
        }
