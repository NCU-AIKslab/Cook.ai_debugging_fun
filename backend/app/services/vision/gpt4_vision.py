"""
GPT-4 Vision Engine

使用 OpenAI GPT-4 Vision API 理解圖片內容
"""
import base64
import logging
from typing import Optional, Dict
from openai import OpenAI

logger = logging.getLogger(__name__)

class GPT4VisionEngine:
    """GPT-4 Vision implementation for image understanding"""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize GPT-4 Vision Engine
        
        Args:
            api_key: OpenAI API key (optional, reads from env if not provided)
            model: Model to use (default: gpt-4o)
        """
        self.client = OpenAI(api_key=api_key)
        self.model = model
        logger.info(f"✅ GPT-4 Vision Engine initialized with model: {model}")
    
    def describe_image(
        self, 
        image_bytes: bytes, 
        prompt: Optional[str] = None,
        max_tokens: int = 500,
        detail: str = "auto"
    ) -> Dict:
        """
        Generate description of image using GPT-4 Vision
        
        Args:
            image_bytes: Image data in bytes
            prompt: Custom prompt (optional, uses default if not provided)
            max_tokens: Maximum tokens in response
            detail: Image detail level ('low', 'high', 'auto')
        
        Returns:
            Dictionary with:
            - description: Image description in Traditional Chinese
            - prompt_tokens: Number of prompt tokens used
            - completion_tokens: Number of completion tokens used
            - total_tokens: Total tokens used
            - model: Model name used
            - cost: Estimated cost in USD
        """
        try:
            # Convert to base64
            b64_image = base64.b64encode(image_bytes).decode('utf-8')
            
            # Default prompt for educational materials
            if prompt is None:
                prompt = """請用繁體中文忠實提取並描述這張教學材料圖片。

**任務**：
1. 逐字提取圖片中的所有文字內容（包括標題、正文、標註、說明等）
2. 保持原有的文字結構和順序，保留編號如 1. 2. 3.
3. 如果是表格，請保留表格結構
4. 在文字提取後，用1-2句話簡要說明圖片元素之間的關係或重點

**輸出格式範例**：
[標題] 如何評估/迭代模型
1. 訓練集
課程講課、自己讀書
2. 驗證集
題目、考古題、模擬考
3. 測試集
期中考、期末考
為了避免作弊，我們需要把資料切成以上3種資料集。

這是進行模型評估的三個資料集，訓練集用於模型的學習，驗證集用於調整模型，測試集用於最終評估。

**注意**：
- 不要輸出"優先任務"、"次要任務"等標題
- 關係說明直接寫出，不要用中括號框住
- 直接輸出結果，不要重複指示內容"""



            
            # Call GPT-4 Vision API
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{b64_image}",
                                "detail": detail
                            }
                        }
                    ]
                }],
                max_tokens=max_tokens
            )
            
            description = response.choices[0].message.content
            usage = response.usage
            
            # Calculate cost
            cost = self._calculate_cost(usage.prompt_tokens, usage.completion_tokens)
            
            # Log token usage
            logger.info(f"GPT-4 Vision: {usage.total_tokens} tokens (${cost:.6f})")
            
            return {
                "description": description.strip(),
                "prompt_tokens": usage.prompt_tokens,
                "completion_tokens": usage.completion_tokens,
                "total_tokens": usage.total_tokens,
                "model": self.model,
                "cost": cost
            }
        
        except Exception as e:
            logger.error(f"GPT-4 Vision failed: {e}")
            return {
                "description": f"[Vision Error: {e}]",
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0,
                "model": self.model,
                "cost": 0.0
            }
    
    def _calculate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """
        Calculate cost based on token usage
        
        Pricing (per 1M tokens):
        - gpt-4o: $5.00 input, $15.00 output
        - gpt-4o-mini: $0.15 input, $0.60 output
        """
        pricing = {
            "gpt-4o": {"input": 5.00, "output": 15.00},
            "gpt-4o-mini": {"input": 0.15, "output": 0.60},
        }
        
        # Get pricing for current model (default to gpt-4o if unknown)
        model_pricing = pricing.get(self.model, pricing["gpt-4o"])
        
        input_cost = (prompt_tokens / 1_000_000) * model_pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * model_pricing["output"]
        
        return input_cost + output_cost
    
    def is_available(self) -> bool:
        """Check if GPT-4 Vision is available"""
        try:
            # Simple check: see if we can create the client
            return self.client is not None
        except:
            return False
