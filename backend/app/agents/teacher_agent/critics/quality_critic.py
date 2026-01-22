import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

RUBRICS = {
    # 情境不完整、專有名詞超出學生學習範圍（需參考 RAG context，而非僅 source.evidence）
    "Understandable": {
        "description": "可理解性 (Understandable)",
        "1": "缺乏必要情境說明，學生無法理解「為什麼要問這個問題」。或使用大量教材（RAG context）中完全未出現的專業術語（4個以上），超出學生學習範圍。",
        "2": "情境說明嚴重不足，僅提供片段訊息。或使用 3 個以上超出教材範圍的專業術語，學生需要額外背景知識才能理解。",
        "3": "提供基本情境，但不夠完整。或有 1-2 個術語超出教材範圍，學生經過推敲可理解題意。",
        "4": "情境說明充足，學生能理解問題背景和目的。所有術語都在教材（RAG context）範圍內，符合學生程度。",
        "5": "提供完整情境和背景說明，學生能清楚理解問題的來龍去脈。術語使用精準且完全符合教材內容和學生程度。"
    },
    
    # 拼寫錯誤、標點符號錯誤
    "Grammatical": {
        "description": "語法正確性 (Grammatical)",
        "1": "存在多個嚴重拼寫錯誤（3個以上），如專業術語拼錯（「P施」應為「PCA」）、關鍵字錯別字。或缺少必要標點符號導致語意不清，句子結構混亂無法理解。",
        "2": "存在 2-3 個明顯的拼寫錯誤或錯別字，或標點使用不當影響閱讀流暢度（如缺少逗號、問號位置錯誤）。句子結構基本正確但略顯生硬。",
        "3": "有 1 個輕微的拼寫錯誤或標點瑕疵，但不影響整體理解。句子結構通順，文筆尚可。",
        "4": "無明顯拼寫或標點錯誤，句子結構流暢，用詞恰當。語法與格式符合學術標準。",
        "5": "語法與格式卓越，文筆流暢且完全正確。標點使用精準，專業術語拼寫完全正確，句子結構優美易讀。"
    },
    
    # 邏輯矛盾、答案與參考資料不一致
    "Logical_Consistency": {
        "description": "邏輯一致性 (Logical Consistency)",
        "1": "正確答案與參考資料（source.evidence 或 RAG context）嚴重矛盾，答案明確錯誤。或題目邏輯混亂，選項之間互相矛盾。",
        "2": "答案與參考資料部分矛盾，或題目邏輯有明顯漏洞。選項設計不當，可能有多個合理答案或無正確答案。",
        "3": "答案與參考資料基本一致，但存在輕微的邏輯瑕疵或不夠精確的表述。選項設計尚可。",
        "4": "答案與參考資料完全一致，邏輯清晰正確。選項設計合理，干擾項有辨識度。",
        "5": "答案與參考資料完美對應，邏輯嚴謹無誤。選項設計優秀，每個選項都有明確的邏輯依據。"
    },
    # 連接詞使用重複性太高、不通順、大陸用語(可能較難判斷，有可能參考資料本身就包含，如果有抓到的話建議一下就好)
    "Phrasing": {
        "description": "措辭正當性 (Phrasing)",
        "1": "用詞明顯不符合繁體中文規範，含有多個簡體中文詞彙（例如：机器学习、数据、质量）。或連接詞使用極度重複，句子嚴重不通順，措辭薄弱影響專業性。",
        "2": "含有少量大陸用語或簡體詞彙。或連接詞使用重複性高（同一連接詞出現3次以上），句子結構略顯生硬不流暢。",
        "3": "用詞基本符合繁體中文規範，但可能有 1-2 處大陸用語（若來源於參考資料則可接受）。連接詞使用尚可，句子通順但缺乏變化。",
        "4": "用詞清晰恰當，符合台灣學術用語習慣。連接詞使用得當，句子流暢有變化。即使參考資料含大陸用語，也已適當轉換。",
        "5": "用詞精準優美，完全符合台灣教育內容規範。連接詞使用靈活多變，句子結構豐富流暢，文筆優秀。"
    },
    "Core Concept Focus": {
        "description": "核心概念聚焦性 (Core Concept Focus)",
        "1": "內容完全偏離核心概念，都在討論次要或無關的細節。",
        "2": "內容有提到核心概念，但花費過多篇幅在次要細節上。",
        "3": "內容有清楚地呈現核心概念。",
        "4": "內容清楚地呈現核心概念，且能區分主次，與學習目標相關。",
        "5": "內容完全聚焦於核心概念，並圍繞其建構出深刻的論述，與學習目標高度對齊。"
    },
    "Would You Use It": {
        "description": "採用意願 (Would You Use It)",
        "1": "完全不會，這份教材毫無用處或充滿錯誤，使用它可能帶來誤導學生的風險。",
        "2": "不會，除非進行大幅度的修改。",
        "3": "會，但在使用前需要進行一些重要的修改。整體品質勉強及格，瑕疵點可修復。",
        "4": "會，只需要進行一些微小的潤飾即可使用。整體品質及格，瑕疵點可修復。",
        "5": "絕對會，這份教材可以直接採用，品質堪比人類專家。沒有發現任何品質瑕疵或潛在風險。"
    }
}

class QualityCritic:
    """
    Evaluates educational content quality using Analyze-rate strategy (based on G-Eval research).
    
    Strategy: Rationale-Based LLM Evaluation Framework
    1. Analyze: LLM analyzes content against rubrics with detailed reasoning
    2. Rate: LLM assigns 1-5 score based on analysis
    3. Suggest: LLM generates improvement suggestions (always present in output)
    
    Key improvements over basic G-Eval:
    - Forces LLM to provide analysis BEFORE rating (rationale-first approach)
    - Requires suggestions field to always exist (enhances output consistency)
    - Strict JSON validation with RFC 8259 compliance
    - Markdown code block wrapping for robust parsing
    """
    def __init__(self, llm: BaseChatModel, threshold: float = 4.0):
        """
        Args:
            llm: Language model for evaluation
            threshold: Score threshold for improvement suggestions emphasis (default 4.0)
        """
        self.llm = llm
        self.threshold = threshold
    
    def _get_criterion_focus(self, criteria: List[str]) -> str:
        """
        Generate criterion-specific focus guidance to separate evaluation responsibilities.
        """
        focus_map = {
            "Understandable": """
**本次評估維度：可理解性 (Understandable)**
- ✅ 僅評估：情境是否完整、術語是否在學生學習範圍內
- ❌ 不評估：答案是否正確、拼寫錯誤、用語規範（這些由其他維度負責）
- 🎯 焦點：「學生是否能理解題目在問什麼、為什麼要問這個問題」

**評估方法：**
1. 檢查題目是否提供充足的背景情境（為什麼要問這個問題？）
2. 對照**檢索到的參考資料**（若有）檢查題目是否遺漏重要背景資訊
3. 檢查專業術語是否在檢索到的參考資料中出現過
4. **不要**僅因「術語在 evidence 中出現」就給高分

**範例：**
❌ 錯誤評估：「術語都在 evidence 中，給5分」
✅ 正確評估：「題目缺少『為什麼薪水有缺失值』、『為什麼選中位數』的背景說明（檢索到的參考資料中有提到），給2分」

📝 即使發現答案矛盾或拼寫錯誤，也應專注於情境完整性評分
""",
            "Grammatical": """
**本次評估維度：語法正確性 (Grammatical)**
- ✅ 僅評估：拼寫錯誤、錯別字、標點符號使用（半形/全形、問號/句號）
- ❌ 不評估：答案正確性、情境完整性、邏輯矛盾（這些由其他維度負責）
- 🎯 焦點：「文字本身是否有錯誤」
- 📝 特別注意：專業術語拼寫（如「P施」應為「PCA」）、全形/半形標點混用
- 📝 即使內容邏輯有問題，只要文字拼寫正確，仍應給高分
""",
            "Logical_Consistency": """
**本次評估維度：邏輯一致性 (Logical_Consistency)**
- ✅ 僅評估：答案與參考資料是否一致、選項邏輯是否合理
- ❌ 不評估：拼寫錯誤、情境完整性、用語規範（這些由其他維度負責）
- 🎯 焦點：「正確答案是否與 evidence/檢索到的參考資料 矛盾」
- 📝 即使題目情境不完整，只要答案與資料一致，仍應給高分
""",
            "Phrasing": """
**本次評估維度：措辭正當性 (Phrasing)**
- ✅ 僅評估：是否使用大陸用語/簡體詞彙、連接詞是否重複、句子是否通順
- ❌ 不評估：答案正確性、拼寫錯誤、情境完整性（這些由其他維度負責）
- 🎯 焦點：「用詞是否符合台灣繁體中文規範、句子是否流暢」
- 📝 特別注意：「机器学习」→「機器學習」、「数据」→「資料」等簡體詞彙
- 📝 若參考資料本身含大陸用語，則可寬鬆看待（在分析中說明）
"""
        }
        
        focus_texts = [focus_map.get(c, "") for c in criteria if c in focus_map]
        return "\n".join(focus_texts)
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def evaluate(self, content: Dict[str, Any], criteria: List[str] = None) -> Dict[str, Any]:
        """
        Evaluates a single content item using Analyze-rate strategy (based on G-Eval).
        
        Args:
            content: Content to evaluate (dict format, will be serialized to JSON)
            criteria: List of criteria names to evaluate. If None, evaluates all rubrics.
        
        Returns:
            Dict with structure:
            {
                "evaluations": [
                    {
                        "criteria": str,
                        "analysis": str (Traditional Chinese),
                        "rating": int (1-5),
                        "suggestions": List[str] (always present, empty if no issues)
                    }
                ]
            }
        """
        if criteria is None:
            criteria = list(RUBRICS.keys())
            
        # Prepare content string
        content_str = json.dumps(content, ensure_ascii=False, indent=2)
        
        # Construct rubric text with evaluation steps
        rubric_sections = []
        for key in criteria:
            if key in RUBRICS:
                r = RUBRICS[key]
                section = f"### {r['description']}\n"
                section += "**評分標準：**\n"
                for score in ["1", "2", "3", "4", "5"]:
                    section += f"- {score} 分：{r[score]}\n"
                rubric_sections.append(section)
        
        rubric_text = "\n".join(rubric_sections)
        
        # Criterion-specific focus guidance
        criterion_focus = self._get_criterion_focus(criteria)
        
        # Improved prompt following Analyze-rate strategy with enhanced robustness
        prompt = f"""你是一位對格式要求極度精確的專業教育內容評估專家。

**你的角色與責任：**
- 使用嚴謹的標準評估教育內容
- 提供詳細的分析作為評分的唯一依據
- 輸出格式必須 100% 符合 JSON 規範

---

**🚨 重要：關於參考資料的來源**

待評估內容中包含兩種參考資料：
1. **`source.evidence`**：由 LLM Generator 自動精簡生成的摘要，**可能不完整或有誤**
2. **檢索到的參考資料**：真正的教材原文內容（若有提供）

**評估優先級：**
- ✅ **優先參考「檢索到的參考資料」**（真實教材）來判斷術語範圍、情境完整性
- ⚠️ **謹慎使用 `source.evidence`**（LLM生成的摘要，可能出錯）
- 📝 若兩者內容不一致，以檢索到的參考資料為準

**範例說明：**
```json
{{
  "source": {{
    "evidence": "薪水列填補為中位數"  // ← LLM 精簡的，可能缺漏情境
  }},
  "檢索到的參考資料": "...薪水欄位有20%缺失值，由於薪水分布有極端值..."  // ← 真實教材
}}
```
→ 評估情境完整性時，應檢查題目是否包含檢索到的參考資料中的背景說明（缺失值、極端值），而非只看 evidence

---

**重要：評估職責分離**

{criterion_focus}

**請嚴格遵守上述職責範圍，不要跨越到其他評估維度。**

---

**評估策略 (Analyze-Rate Strategy):**

本評估採用**基於釋義的 LLM 評估框架 (Rationale-Based Evaluation)**：

1. **分析 (Analyze)**
   - 仔細閱讀待評估內容
   - **僅針對當前評估維度**進行深入、具體的分析
   - 分析必須**引用內容中的具體例子**
   - 分析必須**先於評分**完成，作為評分的唯一依據

2. **評分 (Rate)**
   - 基於分析結果，**僅針對當前維度**給予 1-5 分
   - 評分必須與分析邏輯一致
   - **忽略其他維度的問題**，即使發現了也不應影響當前維度的評分

3. **建議 (Suggest)**
   - **無論分數高低**，都要總結改進空間
   - 若評分 >= {self.threshold}：提供可選的優化建議（可為空）
   - 若評分 < {self.threshold}：必須提供具體、可操作的改進建議

**重要：嚴格評分校準**
請參考以下範例來校準您的評分標準。

**特別注意：本評估的前提是「學生已看過完整教材」，因此：**
1. **不需要**在題目中重複提供完整情境故事
2. **重點檢查**：題目中的專業術語是否在 `source.evidence` 中有出現
3. **嚴格禁止**：使用教材中完全未提及的術語
4. **優先檢查**：正確答案是否與 evidence 矛盾（最嚴重錯誤）

**【1 分範例 A】正確答案與 evidence 矛盾:**
問題：「填補缺失值的方式之一是使用什麼來填補年齡？」
正確答案: A (中位數)
evidence: "年齡 (Age) 列填補為平均值。"
→ **嚴重矛盾**：正確答案是「中位數」，但 evidence 明確說「平均值」
→ 答案與證據完全相反，學生會完全混淆，這是邏輯錯誤
→ **優先偵測此類問題**
→ 評分：**1 分**

**【1 分範例 B】術語完全未在教材出現:**
問題：「在深度學習中，使用 Adam optimizer 的主要優勢為何？」
evidence: "機器學習有多種方法。"
→ **問題**：題目提到「深度學習」、「Adam optimizer」都未在 evidence 中出現
→ 學生即使看過教材也無從得知這些術語
→ 評分：**1 分**

**【2 分範例】多個術語未在教材出現:**
問題：「使用 KNN 算法進行特徵選擇的目的為何？」
evidence: "使用 KNN 算法預測缺失值。"
→ **問題**：「特徵選擇」未在 evidence 中提及（evidence 只說「預測缺失值」）
→ 學生會混淆 KNN 的用途
→ 評分：**2 分**

**【3 分範例】大部分術語有出現:**
問題：「填補缺失值可以使用中位數或平均數，何者較不受極端值影響？」
evidence: "填補缺失值可使用平均數。"
→ **狀況**：evidence 提到「平均數」，但未提及「中位數」和「極端值」
→ 學生看過教材的其他部分可能知道中位數概念
→ 評分：**3 分**

**【4 分範例】所有術語都在教材中:**
問題：「使用 KNN 算法的目的為何？」
evidence: "使用如 KNN（K-Nearest Neighbors）等算法，根據相似記錄來預測缺失值。"
→ **優點**：KNN、預測缺失值都在 evidence 中明確提到
→ 學生看過教材後能直接理解
→ 評分：**4 分**

**評估步驟（針對 Understandable）：**
1. **優先：檢查矛盾**
   - 正確答案是否與 source.evidence 內容相反或矛盾？
   - 若矛盾 → **直接評 1 分**，記錄矛盾點，無需繼續後續檢查
   
2. **提取題目中的專業術語**（包括 question_text 和 options）

3. **檢查 source.evidence**：這些術語是否在 evidence 中出現？

4. **計數未出現的術語**：
   - 4+ 個未出現 → 1 分
   - 3 個未出現 → 2 分  
   - 1-2 個未出現 → 3 分
   - 全部出現 → 4-5 分

---

**評分標準 (Rubrics):**

{rubric_text}

---

**待評估內容:**

{content_str}

---

**輸出格式要求 (CRITICAL - 必須嚴格遵守):**

1. **JSON 標準**：
   - 輸出必須嚴格符合 RFC 8259 標準
   - 所有鍵和字串值必須使用雙引號 `"`
   - 不得使用單引號或其他非標準字符
   - 輸出中不得包含任何額外的解釋性文字

2. **結構要求**：
   - 為**上述 Rubrics 中的每一個評分標準**都產生一個評估物件
   - `suggestions` 欄位必須始終存在
   - 若無建議，`suggestions` 必須為空陣列 `[]`（不可省略此欄位）

3. **Markdown 包裝**：
   - 請將 JSON 輸出包裝在 Markdown 程式碼區塊中：
   ```json
   {{
     "evaluations": [...]
   }}
   ```

**JSON 結構範例：**

```json
{{
  "evaluations": [
    {{
      "criteria": "可理解性 (Understandable)",
      "analysis": "【必填】詳細分析，必須引用內容中的具體例子，說明為何給予此評分。分析應先於評分完成。",
      "rating": 4,
      "suggestions": ["建議1：具體可操作的改進方向", "建議2：..."]
    }},
    {{
      "criteria": "語法正確性 (Grammatical)",
      "analysis": "【必填】語法優秀，無明顯錯誤。",
      "rating": 5,
      "suggestions": []
    }}
  ]
}}
```

**重要提示：**
- 所有文字（analysis, suggestions）必須使用繁體中文
- `analysis` 必須先於 `rating` 思考完成，作為評分的**唯一依據**
- 每個評估物件的 `suggestions` 欄位必須存在（即使為空陣列）
- 輸出的 JSON 必須能被 Python 的 `json.loads()` 直接解析，不得有任何語法錯誤

現在請開始評估，並以上述 JSON 格式輸出結果。
"""
        
        messages = [HumanMessage(content=prompt)]
        
        try:
            # Call LLM with temperature=0 for consistency
            response = await self.llm.ainvoke(messages)
            output = response.content.strip()
            
            # Parse JSON from response
            parsed = self._parse_json_response(output)
            
            # Validate structure
            if "evaluations" not in parsed:
                raise ValueError("Response missing 'evaluations' key")
            
            # Strict validation: ensure all evaluations have required fields
            for i, eval_item in enumerate(parsed["evaluations"]):
                if "criteria" not in eval_item:
                    raise ValueError(f"Evaluation {i} missing 'criteria' field")
                if "analysis" not in eval_item:
                    raise ValueError(f"Evaluation {i} missing 'analysis' field")
                if "rating" not in eval_item:
                    raise ValueError(f"Evaluation {i} missing 'rating' field")
                
                # CRITICAL: suggestions must always exist (even if empty)
                if "suggestions" not in eval_item:
                    logger.warning(f"Evaluation {i} missing 'suggestions', adding empty array")
                    eval_item["suggestions"] = []
                
                # Validate rating range
                rating = eval_item.get("rating", 0)
                if not isinstance(rating, int) or rating < 1 or rating > 5:
                    raise ValueError(f"Invalid rating {rating} in evaluation {i}, must be 1-5")
            
            return parsed
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse LLM JSON output: {e}\nRaw output: {output[:500]}")
            return {
                "error": "JSON parsing failed",
                "raw_output": output,
                "evaluations": []
            }
        except Exception as e:
            logger.error(f"Error in evaluation: {e}")
            return {
                "error": str(e),
                "evaluations": []
            }

    def _parse_json_response(self, output: str) -> Dict[str, Any]:
        """
        Parse JSON from LLM response, handling code blocks.
        """
        # Remove markdown code blocks if present
        if "```json" in output:
            output = output.split("```json")[1].split("```")[0].strip()
        elif "```" in output:
            # Try to extract content between first pair of ```
            parts = output.split("```")
            if len(parts) >= 3:
                output = parts[1].strip()
        
        # Parse JSON
        return json.loads(output)

    async def batch_evaluate(self, content_list: List[Dict[str, Any]], criteria: List[str] = None) -> List[Dict[str, Any]]:
        """
        Evaluate multiple content items.
        
        Args:
            content_list: List of content items to evaluate
            criteria: Criteria to use for all evaluations
        
        Returns:
            List of evaluation results, one per content item
        """
        results = []
        for content in content_list:
            result = await self.evaluate(content, criteria)
            results.append(result)
        return results

    async def evaluate_exam(
        self, 
        exam: Dict[str, Any], 
        rag_content: str = None,
        criteria: List[str] = None,
        mode: str = "quick"
    ) -> Dict[str, Any]:
        """
        Evaluate an entire exam with different evaluation modes.
        
        Args:
            exam: Exam content with structure:
                {
                    "type": "multiple_choice" or "exam",
                    "questions": [
                        {"question_number": 1, "question_text": "...", ...},
                        {"question_number": 2, ...},
                        ...
                    ]
                }
            rag_content: Optional RAG context (retrieved educational material)
            criteria: List of criteria names to evaluate. If None, evaluates all rubrics.
            mode: Evaluation mode:
                - "quick" (default): Only overall evaluation, cost-effective
                - "comprehensive": Overall + per-question + statistics
        
        Returns:
            Dict with structure:
            {
                "mode": str,                # Evaluation mode used
                "overall": {...},           # Overall exam assessment
                "per_question": [...],      # Individual assessments (comprehensive only)
                "statistics": {...}         # Summary statistics (comprehensive only)
            }
        
        Example:
            # Quick mode (default)
            result = await critic.evaluate_exam(exam, rag_content="...", mode="quick")
            
            # Comprehensive mode
            result = await critic.evaluate_exam(exam, rag_content="...", mode="comprehensive")
        """
        # Add rag_content to exam if provided
        if rag_content:
            exam["rag_content"] = rag_content
        
        all_questions = exam.get("questions", [])
        results = {"mode": mode}
        
        # 1. Overall exam evaluation (always performed)
        logger.info(f"[{mode.upper()} MODE] Evaluating exam with {len(all_questions)} questions at exam-level")
        results["overall"] = await self.evaluate(exam, criteria)
        
        # 2. Per-question evaluation (comprehensive mode only)
        if mode == "comprehensive":
            logger.info(f"[COMPREHENSIVE MODE] Evaluating all {len(all_questions)} questions individually")
            
            # Create evaluation tasks for all questions (concurrent)
            eval_tasks = []
            for q in all_questions:
                single_q = {
                    "type": "multiple_choice",
                    "questions": [q]
                }
                # Pass rag_content to individual questions too
                if rag_content:
                    single_q["rag_content"] = rag_content
                eval_tasks.append(self.evaluate(single_q, criteria))
            
            # Execute all evaluations concurrently
            question_results = await asyncio.gather(*eval_tasks, return_exceptions=True)
            
            # Format results
            results["per_question"] = []
            for i, (q, q_result) in enumerate(zip(all_questions, question_results)):
                if isinstance(q_result, Exception):
                    logger.error(f"Error evaluating question {q.get('question_number', i+1)}: {q_result}")
                    results["per_question"].append({
                        "question_type": q.get("question_type", "unknown"),
                        "question_number": q.get("question_number", i + 1),
                        "error": str(q_result),
                        "evaluations": []
                    })
                else:
                    results["per_question"].append({
                        "question_type": q.get("question_type", "unknown"),
                        "question_number": q.get("question_number", i + 1),
                        "evaluations": q_result.get("evaluations", [])
                    })
            
            # Compute statistics
            results["statistics"] = self._compute_exam_statistics(results["per_question"])
        else:
            logger.info(f"[QUICK MODE] Skipping per-question evaluation")
            results["per_question"] = []
            results["statistics"] = {
                "note": f"Per-question evaluation skipped in {mode} mode"
            }
        
        return results
    
    async def evaluate_single_question(
        self,
        question: Dict[str, Any],
        rag_content: str = None,
        criteria: List[str] = None
    ) -> Dict[str, Any]:
        """
        Evaluate a single question.
        
        This is a simplified API for unit testing individual questions.
        
        Args:
            question: Single question dict with structure:
                {
                    "question_number": 1,
                    "question_text": "...",
                    "options": {"A": "...", "B": "..."},
                    "correct_answer": "A",
                    "source": {"page_number": "...", "evidence": "..."}
                }
            rag_content: Optional RAG context (retrieved educational material)
            criteria: List of criteria names to evaluate. If None, evaluates all rubrics.
        
        Returns:
            Dict with evaluation results for the single question
        
        Example:
            result = await critic.evaluate_single_question(question, rag_content="...")
        """
        # Wrap question in expected format
        content = {
            "type": "multiple_choice",
            "questions": [question]
        }
        
        # Add rag_content if provided
        if rag_content:
            content["rag_content"] = rag_content
        
        # Evaluate using the core evaluate method
        return await self.evaluate(content, criteria)
    
    def _compute_exam_statistics(self, per_question_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute summary statistics from per-question evaluation results.
        
        Args:
            per_question_results: List of per-question evaluation results
        
        Returns:
            Dict containing statistics:
            {
                "total_questions": int,
                "avg_scores_by_criteria": {"Understandable": 3.5, ...},
                "min_scores_by_criteria": {"Understandable": 2, ...},
                "max_scores_by_criteria": {"Understandable": 5, ...},
                "questions_below_threshold": [1, 3, 5]  # Question numbers
            }
        """
        if not per_question_results:
            return {}
        
        # Aggregate scores by criteria
        criteria_scores = {}
        questions_below_threshold = []
        
        for q_result in per_question_results:
            if "error" in q_result or not q_result.get("evaluations"):
                continue
            
            question_num = q_result.get("question_number")
            has_low_score = False
            
            for eval_item in q_result["evaluations"]:
                criteria = eval_item.get("criteria")
                rating = eval_item.get("rating", 0)
                
                if criteria:
                    if criteria not in criteria_scores:
                        criteria_scores[criteria] = []
                    criteria_scores[criteria].append(rating)
                
                # Check if any score is below threshold
                if rating < self.threshold:
                    has_low_score = True
            
            if has_low_score and question_num:
                questions_below_threshold.append(question_num)
        
        # Compute statistics
        stats = {
            "total_questions": len(per_question_results),
            "avg_scores_by_criteria": {},
            "min_scores_by_criteria": {},
            "max_scores_by_criteria": {},
            "questions_below_threshold": questions_below_threshold
        }
        
        for criteria, scores in criteria_scores.items():
            if scores:
                stats["avg_scores_by_criteria"][criteria] = round(sum(scores) / len(scores), 2)
                stats["min_scores_by_criteria"][criteria] = min(scores)
                stats["max_scores_by_criteria"][criteria] = max(scores)
        
        return stats
