# Graph 內建 Critic Loop - 完整實現規劃

> **日期**: 2025-12-09  
> **狀態**: Ready for Implementation

---

## 目錄

1. [目標與核心流程](#目標與核心流程)
2. [State 管理](#state-管理)
3. [Multi-Critic 架構](#multi-critic-架構)
4. [Skill 可擴充性設計](#skill-可擴充性設計)
5. [統一的 Refinement 機制](#統一的-refinement-機制)
6. [數據記錄優化](#數據記錄優化)
7. [API 輸出設計](#api-輸出設計)
8. [前端可視化支持](#前端可視化支持)
9. [性能優化](#性能優化)
10. [實現步驟](#實現步驟)
11. [配置參數](#配置參數)

---

## 目標與核心流程

### 目標

將 `test_critic_workflow` 升級為完整的 Graph 內建 Critic Loop，實現：
- ✅ 自動品質檢查與迭代改進
- ✅ **多 Critic 支持**（Fact + Quality，可選）
- ✅ 完整的實驗數據記錄與前端可視化支持
- ✅ 智能 RAG 快取與部分重新生成優化
- ✅ **可擴充的 Skill 架構**（支持未來新增 skills）

### 核心流程設計

```
教師輸入指令 
  ↓
Router (路由到技能)
  ↓
Skill (exam/summary 生成) - Iteration 1
  ↓
Fact Critic (事實性檢查) ← 用戶可選 ⚠️ 先執行
  ↓
Quality Critic (品質評估) ← 用戶可選
  ↓
Decision Point (should_continue_from_critic)
  ├─ 通過 (is_passed=True) → Aggregate Output
  │   └─ 返回: 最終結果 + 完整評分歷史 + 改進摘要
  ├─ 失敗但未達上限 → 回到 Skill (帶 feedback)
  │   └─ Skill 接收 feedback，進行智能改進 → Iteration 2 → Critic
  └─ 失敗且達上限 → Aggregate Output
      └─ 返回: 最終結果 + 完整評分 + 失敗分析與建議
```

#### 關鍵設計決策

1. **Critic 執行順序**: Fact → Quality  
   - **原因**: 事實正確性是基礎，先確保內容事實無誤，再評估品質

2. **失敗時完整輸出**  
   - 無論通過或失敗，都返回完整結果 + 分數 + 建議
   - 達上限時標記為 `partial_success`，但仍提供最終內容

3. **統一的 Refinement 設計**  
   - 不新增獨立的 refinement nodes
   - 在現有 generation nodes 中加入 refinement 邏輯
   - 根據 `is_refinement` 標誌決定行為

---

## State 管理

### TeacherAgentState 新增/修改欄位

```python
# graph.py - TeacherAgentState
class TeacherAgentState(TypedDict):
    # ... 現有欄位 ...
    
    # === Critic 配置 ===
    enabled_critics: List[str]  # ["fact", "quality"] - 用戶可選擇啟用哪些 critic
    critic_mode: str  # "quick" or "comprehensive"
    
    # === 迭代管理 ===
    iteration_count: int  # 當前迭代次數 (預設 1)
    max_iterations: int  # 最大迭代次數 (預設 3)
    
    # === Critic Feedback (統一格式) ===
    critic_feedback: List[Dict]  # 每次迭代的評估結果
    # 格式示例:
    # [
    #   {
    #     "iteration": 1,
    #     "critics": {
    #       "fact": {"is_passed": True, "scores": {...}, "feedback": {...}},
    #       "quality": {"is_passed": False, "scores": {...}, "feedback": {...}}
    #     },
    #     "overall_passed": False,  # 需全部通過才為 True
    #     "timestamp": "2025-12-09T15:00:00+08:00"
    #   }
    # ]
    
    critic_passed: bool  # 最新一次是否全部通過
    critic_metrics: Dict  # 最新一次的綜合指標
    
    # === 版本追蹤 ===
    generation_history: List[Dict]  # 每個版本的生成內容
    # 格式示例:
    # [
    #   {
    #     "iteration": 1,
    #     "content": [...],
    #     "task_id": 1234,
    #     "timestamp": "2025-12-09T15:00:00+08:00"
    #   }
    # ]
    
    # === RAG 快取 ✅ ===
    rag_cache: Dict  # 快取 RAG 檢索結果，避免重複檢索
    # 格式:
    # {
    #   "text_chunks": [...],
    #   "page_content": [...],
    #   "cached_at": "2025-12-09T15:00:00+08:00"
    # }
```

### Sub-graph States (ExamGenerationState / SummarizationState)

```python
# 這些 sub-graph states 也需要支持 refinement
class ExamGenerationState(TypedDict):
    # ... 現有欄位 ...
    
    # === Refinement 支持 ===
    is_refinement: bool  # 是否為 refinement iteration
    refinement_feedback: Dict  # Critic 提供的具體改進建議
    previous_content: List[Dict]  # 上一版本的內容（用於對比）
    
    # === RAG 快取 ===
    use_cached_rag: bool  # 是否使用快取的 RAG 結果
    cached_rag_data: Dict  # 從 parent state 傳入的快取數據
```

---

## Multi-Critic 架構

### Critic 執行流程

```python
# graph.py - run_critics_node

@log_task(
    agent_name="critics_evaluation",
    task_description="Run enabled critics sequentially (fact → quality)",
    input_extractor=lambda state: {
        "enabled_critics": state.get("enabled_critics", []),
        "iteration": state.get("iteration_count", 1)
    }
)
async def run_critics_node(state: TeacherAgentState) -> dict:
    """
    根據 enabled_critics 依序執行對應的 critic
    
    執行順序: Fact Critic → Quality Critic ⚠️
    原因: 事實正確性是基礎，先確保內容事實無誤
    
    執行邏輯:
    1. 依序執行啟用的 critics
    2. 收集所有評估結果
    3. 綜合判斷是否通過（需全部通過才算通過）
    """
    enabled_critics = state.get("enabled_critics", ["quality"])
    iteration = state.get("iteration_count", 1)
    
    critics_results = {}
    overall_passed = True
    
    # 1. 執行 Fact Critic (優先) ⚠️
    if "fact" in enabled_critics:
        logger.info("🔍 Running Fact Critic...")
        fact_result = await run_fact_critic(state)
        critics_results["fact"] = fact_result
        if not fact_result.get("is_passed"):
            overall_passed = False
            logger.warning("❌ Fact Critic failed")
    
    # 2. 執行 Quality Critic
    if "quality" in enabled_critics:
        logger.info("✨ Running Quality Critic...")
        quality_result = await run_quality_critic(state)
        critics_results["quality"] = quality_result
        if not quality_result.get("is_passed"):
            overall_passed = False
            logger.warning("❌ Quality Critic failed")
    
    # 3. 構建綜合 feedback
    combined_feedback = {
        "iteration": iteration,
        "critics": critics_results,
        "overall_passed": overall_passed,
        "timestamp": datetime.now(TAIPEI_TZ).isoformat()
    }
    
    # 4. 更新 feedback history
    feedback_history = state.get("critic_feedback", [])
    feedback_history.append(combined_feedback)
    
    logger.info(f"📊 Iteration {iteration} evaluation complete: {'✅ Passed' if overall_passed else '❌ Failed'}")
    
    return {
        "critic_passed": overall_passed,
        "critic_feedback": feedback_history,
        "critic_metrics": _aggregate_metrics(critics_results)
    }
```

### Critic Helper Functions

```python
async def run_quality_critic(state: TeacherAgentState) -> dict:
    """
    執行 Quality Critic - 從現有邏輯抽取
    
    Returns:
        {
            "is_passed": bool,
            "scores": {...},
            "feedback": {...},
            "failed_criteria": [...]
        }
    """
    # 從現有的 quality_critic_node 抽取邏輯
    pass

async def run_fact_critic(state: TeacherAgentState) -> dict:
    """
    執行 Fact Critic - 未來實現
    
    檢查內容的事實性:
    - 答案與證據是否一致
    - 引用來源是否正確
    - 數據是否準確
    
    Returns:
        {
            "is_passed": bool,
            "scores": {...},
            "feedback": {...},
            "factual_errors": [...]
        }
    """
    # TODO: 未來實現
    # 暫時返回 pass
    return {"is_passed": True, "scores": {}, "feedback": {}}

def _aggregate_metrics(critics_results: Dict) -> dict:
    """
    綜合多個 critic 的指標
    
    Returns:
        {
            "is_passed": bool,
            "failed_critics": ["quality"],  # 失敗的 critics
            "failed_criteria": ["factual_accuracy", "clarity"],  # 所有失敗的標準
            "overall_scores": {...},  # 綜合分數
            "improvement_suggestions": "..."  # 綜合建議
        }
    """
    is_passed = all(r.get("is_passed", False) for r in critics_results.values())
    
    failed_critics = [
        name for name, result in critics_results.items()
        if not result.get("is_passed", False)
    ]
    
    failed_criteria = []
    for result in critics_results.values():
        failed_criteria.extend(result.get("failed_criteria", []))
    
    # 去重
    failed_criteria = list(set(failed_criteria))
    
    return {
        "is_passed": is_passed,
        "failed_critics": failed_critics,
        "failed_criteria": failed_criteria,
        "overall_scores": {
            name: result.get("scores", {})
            for name, result in critics_results.items()
        },
        "improvement_suggestions": _combine_suggestions(critics_results)
    }

def _combine_suggestions(critics_results: Dict) -> str:
    """合併所有 critics 的建議"""
    suggestions = []
    for name, result in critics_results.items():
        if not result.get("is_passed"):
            suggestions.append(f"[{name.upper()}] {result.get('feedback', {}).get('overall_feedback', '')}")
    return "\n".join(suggestions)
```

---

## Skill 可擴充性設計

### 問題

目前的設計只考慮了 exam 和 summary，沒有考慮：
- `general_chat_skill` 不需要 critic 評估
- 未來可能新增的 skills

### 解決方案：Skill Capability 系統

#### A. Skill 配置定義

```python
# skills/base.py (新增檔案)

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
    # 未來新增 skill 時，在這裡添加配置即可
}
```

#### B. 動態的 Graph Edges

```python
# graph.py

def build_skill_to_critic_edges(builder: StateGraph, skill_configs: Dict):
    """
    根據 skill 配置動態建立 edges
    
    優點:
    - 新增 skill 時不需要修改 graph 建構邏輯
    - 配置集中管理
    - 易於維護
    """
    for skill_name, config in skill_configs.items():
        if config.supports_critic:
            # 需要 critic 的 skill → critics
            builder.add_edge(skill_name, "critics")
            logger.info(f"✓ {skill_name} → critics")
        else:
            # 不需要 critic 的 skill → aggregate_output
            builder.add_edge(skill_name, "aggregate_output")
            logger.info(f"✓ {skill_name} → aggregate_output (bypass critic)")

# 使用
from backend.app.agents.teacher_agent.skills.base import SKILL_CONFIGS
build_skill_to_critic_edges(builder, SKILL_CONFIGS)
```

#### C. 動態的 Conditional Edge

```python
def should_continue_from_critic(state: TeacherAgentState) -> str:
    """
    決定 critic 之後的流向
    
    動態檢查 skill 是否支持 refinement
    """
    # 1. 檢查是否通過
    if state.get("critic_passed", False):
        logger.info("✅ All critics passed, proceeding to output")
        return "aggregate_output"
    
    # 2. 檢查迭代次數
    iteration = state.get("iteration_count", 1)
    max_iter = state.get("max_iterations", 3)
    
    if iteration >= max_iter:
        logger.warning(f"⚠️ Max iterations ({max_iter}) reached")
        logger.info("Proceeding to output with partial success status")
        return "aggregate_output"
    
    # 3. 增加迭代計數
    state["iteration_count"] = iteration + 1
    
    # 4. 動態檢查 skill 是否支持 refinement ✅
    last_skill = state.get("next_node")
    skill_config = SKILL_CONFIGS.get(last_skill)
    
    if skill_config and skill_config.supports_refinement:
        logger.info(f"🔄 Iteration {iteration + 1}: Returning to {last_skill}")
        logger.info(f"   Strategy: {skill_config.refinement_strategy}")
        return last_skill
    else:
        logger.warning(f"⚠️ Skill {last_skill} doesn't support refinement")
        logger.info("Ending loop and proceeding to output")
        return "aggregate_output"
```

#### D. 條件式 Critic Edges（未來優化）

```python
# 未來可以進一步動態化
builder.add_conditional_edges(
    "critics",
    should_continue_from_critic,
    {
        "aggregate_output": "aggregate_output",
        **{
            skill_name: skill_name
            for skill_name, config in SKILL_CONFIGS.items()
            if config.supports_refinement
        }
    }
)
```

---

## 統一的 Refinement 機制

### 設計理念

- ✅ **不新增專門的 refinement nodes**
- ✅ **在現有的 generation nodes 中加入 refinement 邏輯**
- ✅ 根據 `is_refinement` 標誌決定執行初次生成或改進
- ✅ 未來可讓教師直接輸入建議進入 refinement 模式

### A. Exam Generation Skill 改進

#### 1. RAG 檢索 with 快取

```python
# exam_nodes.py - retrieve_chunks_node

@log_task(...)
def retrieve_chunks_node(state: ExamGenerationState) -> dict:
    """
    RAG 檢索 with 快取支持 ✅
    """
    # 檢查是否使用快取
    if state.get("use_cached_rag") and state.get("cached_rag_data"):
        logger.info("📦 Using cached RAG results (saved tokens & time)")
        cached_data = state["cached_rag_data"]
        
        return {
            "retrieved_text_chunks": cached_data["text_chunks"],
            "retrieved_page_content": cached_data["page_content"],
            "generation_plan": [],
            "final_generated_content": [],
            "generation_errors": [],
            "parent_task_id": state["current_task_id"]
        }
    
    # 否則正常檢索
    try:
        logger.info("🔍 Retrieving RAG context from database...")
        rag_results = rag_agent.search(
            user_prompt=state["query"],
            unique_content_id=state["unique_content_id"]
        )
        log_task_sources(state["current_task_id"], rag_results["text_chunks"])
        
        return {
            "retrieved_text_chunks": rag_results["text_chunks"],
            "retrieved_page_content": rag_results["page_content"],
            "generation_plan": [],
            "final_generated_content": [],
            "generation_errors": [],
            "parent_task_id": state["current_task_id"]
        }
    except Exception as e:
        return {"error": f"Failed to retrieve context: {str(e)}"}
```

#### 2. Plan Generation with Refinement

```python
@log_task(
    agent_name="plan_or_refine_exam",
    task_description="Create generation plan or refinement plan",
    input_extractor=lambda state: {
        "query": state.get("query"),
        "is_refinement": state.get("is_refinement", False),
        "iteration": state.get("iteration_count", 1)
    }
)
def plan_generation_tasks_node(state: ExamGenerationState) -> dict:
    """
    統一處理初次生成和 refinement
    """
    # === Refinement Mode === ✅
    if state.get("is_refinement"):
        feedback = state.get("refinement_feedback", {})
        previous_content = state.get("previous_content", [])
        
        iteration = state.get("iteration_count", 1)
        logger.info(f"🔧 Refinement mode: Iteration {iteration}")
        logger.info(f"   Previous content: {len(previous_content)} sections")
        
        # 解析 feedback，找出需要改進的題目
        failed_questions = _extract_failed_questions(feedback, previous_content)
        
        if not failed_questions:
            # 沒有具體失敗題目，全部重新生成
            logger.info("⚠️ No specific failed questions identified, regenerating all")
            return _create_initial_plan(state["query"], state)
        
        # 只重新生成失敗的題目 ✅
        logger.info(f"📋 Creating refinement plan for {len(failed_questions)} questions")
        refinement_plan = _create_refinement_plan(
            failed_questions=failed_questions,
            feedback=feedback
        )
        
        llm = get_llm()
        return {
            "generation_plan": refinement_plan,
            "parent_task_id": state["current_task_id"],
            "model_name": llm.model_name
        }
    
    # === Initial Generation Mode ===
    else:
        logger.info("✨ Initial generation mode")
        return _create_initial_plan(state["query"], state)

def _create_initial_plan(query: str, state: ExamGenerationState) -> dict:
    """初次生成的計劃創建邏輯（現有邏輯）"""
    # ... 現有的 plan generation 邏輯 ...
    pass
```

#### 3. Helper Functions

```python
def _extract_failed_questions(feedback: Dict, previous_content: List) -> List[Dict]:
    """
    從 feedback 中提取需要改進的題目
    
    Args:
        feedback: Critic 返回的 feedback
        previous_content: 上一版本的內容
    
    Returns:
        [
            {
                "question_index": 1,
                "question_type": "multiple_choice",
                "original_question": {...},
                "issues": ["factual_accuracy", "clarity"],
                "suggestions": "題目1的答案與證據衝突..."
            }
        ]
    """
    failed_questions = []
    
    # 解析 per-question feedback
    feedback_items = feedback.get("critics", {}).get("quality", {}).get("feedback", {}).get("per_question", [])
    
    for item in feedback_items:
        if item.get("status") == "fail":
            question_index = item["question_index"]
            failed_questions.append({
                "question_index": question_index,
                "question_type": item.get("question_type"),
                "original_question": _find_question_by_index(
                    question_index, previous_content
                ),
                "issues": item.get("failed_criteria", []),
                "suggestions": item.get("improvement_suggestions", "")
            })
    
    return failed_questions

def _find_question_by_index(index: int, content: List) -> Dict:
    """從內容中找出指定索引的題目"""
    for section in content:
        if section.get("type") in ["multiple_choice", "short_answer", "true_false"]:
            for q in section.get("questions", []):
                if q.get("question_number") == index:
                    return q
    return {}

def _create_refinement_plan(failed_questions: List, feedback: Dict) -> List[Dict]:
    """
    為失敗的題目創建改進計劃
    
    策略: 按題目類型分組，為每種類型創建一個 refinement task
    """
    refinement_tasks = []
    
    # 按題目類型分組
    by_type = {}
    for q in failed_questions:
        q_type = q["question_type"]
        if q_type not in by_type:
            by_type[q_type] = []
        by_type[q_type].append(q)
    
    # 為每種類型創建一個 task
    for q_type, questions in by_type.items():
        refinement_tasks.append({
            "type": f"refine_{q_type}",  # "refine_multiple_choice"
            "count": len(questions),
            "questions_to_refine": questions,
            "feedback_summary": feedback.get("improvement_suggestions", "")
        })
    
    return refinement_tasks
```

#### 4. Generation with Refinement

```python
def _generic_generate_question(state: ExamGenerationState, task_type_name: str) -> dict:
    """
    統一的題目生成邏輯，支持 refinement
    """
    current_task = state.get("current_task", {})
    
    # === Refinement Mode === ✅
    if current_task.get("type", "").startswith("refine_"):
        logger.info(f"🔧 Refining {task_type_name} questions")
        
        questions_to_refine = current_task.get("questions_to_refine", [])
        feedback_summary = current_task.get("feedback_summary", "")
        
        # 構建 refinement prompt
        system_prompt = """You are refining exam questions based on critic feedback.
Your goal is to address all identified issues while maintaining the question structure."""

        issues_list = []
        for q in questions_to_refine:
            issues_list.append(f"- Question {q['question_index']}: {', '.join(q['issues'])}")
        
        human_prompt = f"""
**REFINEMENT TASK**

Previous questions had the following issues:
{chr(10).join(issues_list)}

**Overall Feedback:**
{feedback_summary}

**Questions to improve:**
{json.dumps([q["original_question"] for q in questions_to_refine], ensure_ascii=False, indent=2)}

**Instructions:**
Please regenerate these questions, addressing ALL the issues mentioned above.
Maintain the same format (multiple choice/short answer/true-false) but improve:
{', '.join(set(issue for q in questions_to_refine for issue in q["issues"]))}

Ensure:
1. Factual accuracy with proper evidence
2. Clear and unambiguous wording
3. Proper citation of sources
4. All output in Traditional Chinese
"""
        
        # 呼叫 LLM 改進（類似現有邏輯）
        llm = get_llm()
        # ... 構建 messages, 呼叫 tool_llm.invoke, 解析結果 ...
        # ... 計算 tokens 和 cost ...
        
        return {
            "final_generated_content": refined_content,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost,
            "model_name": model_name
        }
    
    # === Initial Generation Mode ===
    else:
        # 現有邏輯保持不變
        # ... (現有的生成邏輯) ...
        pass
```

### B. Summarization Skill 改進

Summary 沒有「部分改進」的概念，**每次都完整重新生成**。

```python
@log_task(...)
def summarize_node(state: SummarizationState) -> dict:
    """
    生成摘要 with refinement 支持
    """
    # === Refinement Mode === ✅
    if state.get("is_refinement"):
        feedback = state.get("refinement_feedback", {})
        previous_summary = state.get("previous_content")
        
        logger.info("🔧 Refinement mode: Regenerating entire summary")
        logger.info("   (Summary is a whole, cannot partially refine)")
        
        # 構建 refinement prompt（包含之前的摘要和 feedback）
        system_prompt = """You are refining a summary based on critic feedback.
Your goal is to improve the summary while addressing all identified issues."""
        
        human_prompt = f"""
**REFINEMENT TASK**

**Previous summary:**
{json.dumps(previous_summary, ensure_ascii=False, indent=2)}

**Feedback from critics:**
{json.dumps(feedback.get("improvement_suggestions", ""), ensure_ascii=False, indent=2)}

**Issues to fix:**
{', '.join(feedback.get("failed_criteria", []))}

**Instructions:**
Please regenerate the ENTIRE summary, addressing all the issues mentioned.
Ensure:
1. All feedback points are addressed
2. Structure is clear and logical
3. Key points are comprehensive
4. Output in Traditional Chinese
5. Use the SummaryReport tool to format your response
"""
        
        # 呼叫 LLM（邏輯類似初次生成，但 prompt 不同）
        llm = get_llm()
        # ... 構建 messages, 呼叫 tool_llm.invoke, 解析結果 ...
        # ... 計算 tokens 和 cost ...
        
        return {
            "final_generated_content": refined_summary,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "estimated_cost_usd": estimated_cost,
            "model_name": model_name,
            "parent_task_id": state.get("current_task_id")
        }
    
    # === Initial Generation Mode ===
    else:
        # 現有邏輯保持不變
        # ... (現有的生成邏輯) ...
        pass
```

### C. General Chat Skill

**不支持 refinement**，因為是對話性質。

```python
# general_chat_node 保持不變
# 在 graph 中直接 bypass critics
builder.add_edge("general_chat_skill", "aggregate_output")
```

---

## Skill Wrapper 改進（傳遞 Refinement Context）

```python
# graph.py

@log_task(...)
def exam_skill_node(state: TeacherAgentState) -> dict:
    """
    Exam skill wrapper - 傳遞 refinement context 和 RAG 快取
    """
    try:
        iteration = state.get("iteration_count", 1)
        is_refinement = iteration > 1
        
        logger.info(f"{'🔧 Refinement' if is_refinement else '✨ Initial'} call to exam generation skill")
        
        skill_input = {
            "job_id": state["job_id"],
            "query": state["user_query"],
            "unique_content_id": state["unique_content_id"],
            "parent_task_id": state.get("current_task_id"),
            
            # Refinement 支持
            "is_refinement": is_refinement,
            "iteration_count": iteration,
        }
        
        # 如果是 refinement，傳遞 feedback 和 previous content
        if is_refinement:
            logger.info("   Passing feedback and previous content to skill")
            latest_feedback = state.get("critic_feedback", [])[-1]
            skill_input["refinement_feedback"] = latest_feedback
            
            # 從 generation_history 取得上一版本
            history = state.get("generation_history", [])
            if history:
                skill_input["previous_content"] = history[-1]["content"]
        
        # RAG 快取 ✅
        if iteration > 1 and state.get("rag_cache"):
            logger.info("   Using cached RAG results")
            skill_input["use_cached_rag"] = True
            skill_input["cached_rag_data"] = state["rag_cache"]
        
        final_skill_state = exam_generator_app.invoke(skill_input)
        
        if final_skill_state.get("error"):
            raise Exception(f"Exam generator failed: {final_skill_state['error']}")
        
        # 記錄到 generation_history
        generated_content = final_skill_state.get("final_generated_content")
        history = state.get("generation_history", [])
        history.append({
            "iteration": iteration,
            "content": generated_content,
            "task_id": state.get("current_task_id"),
            "timestamp": datetime.now(TAIPEI_TZ).isoformat()
        })
        
        # 建立 RAG 快取（第一次迭代）
        rag_cache = state.get("rag_cache")
        if not rag_cache and final_skill_state.get("retrieved_text_chunks"):
            logger.info("💾 Caching RAG results for future iterations")
            rag_cache = {
                "text_chunks": final_skill_state["retrieved_text_chunks"],
                "page_content": final_skill_state["retrieved_page_content"],
                "cached_at": datetime.now(TAIPEI_TZ).isoformat()
            }
        
        return {
            "final_result": final_skill_state,
            "final_generated_content": generated_content,
            "generation_history": history,
            "rag_cache": rag_cache,
            "parent_task_id": state.get("current_task_id")
        }
    
    except Exception as e:
        logger.error(f"Exam skill node failed: {e}")
        return {"error": str(e)}
```

同樣的邏輯應用於 `summarization_skill_node`。

---

## 數據記錄優化

### A. 迭代次數記錄 ✅

在 `create_task` 調用時傳遞 `iteration_number`：

```python
# db_logger.py - log_task decorator

# Async wrapper
task_id = create_task(
    job_id=state["job_id"],
    agent_name=agent_name,
    task_description=task_description,
    task_input=extracted_input,
    parent_task_id=parent_task_id,
    iteration_number=state.get("iteration_count", 1),  # ✅ 加這行
    model_name=None  # 將在 update_task 時更新
)

# Sync wrapper 同樣修改
```

### B. Evaluation 關聯

**當前狀態**: 
- `task_evaluations.task_id` → critic task 的 ID
- critic task 的 `parent_task_id` → generator task 的 ID

**關聯查詢**:
```sql
-- 查詢某 job 的所有 evaluations
SELECT 
    at_gen.id as generator_task_id,
    at_gen.agent_name as generator,
    at_gen.iteration_number,
    at_critic.id as critic_task_id,
    te.is_passed,
    te.metric_details
FROM agent_tasks at_gen
JOIN agent_tasks at_critic ON at_critic.parent_task_id = at_gen.id
JOIN task_evaluations te ON te.task_id = at_critic.id
WHERE at_gen.job_id = 280
ORDER BY at_gen.iteration_number;
```

**結論**: 現有結構已足夠，不需要額外欄位。

---

## API 輸出設計

### `test_critic_workflow` 最終輸出

```python
{
    "job_id": 280,
    "status": "completed",  # or "partial_success" if failed after max iterations
    
    # === 1. 最終結果（無論pass或fail都返回）===
    "final_result": {
        "content": [...],  # 最終版本的內容
        "title": "機器學習基礎測驗",
        "display_type": "exam_questions",
        "iteration": 2  # 最終版本的迭代次數
    },
    
    # === 2. Critic 摘要（前端可視化用）===
    "critic_summary": {
        "total_iterations": 2,
        "final_passed": True,  # or False
        "enabled_critics": ["fact", "quality"],
        
        # 完整的分數歷史（所有迭代）✅
        "scores_history": [
            {
                "iteration": 1,
                "critics": {
                    "fact": {
                        "overall_score": 4.0,
                        "dimension_scores": {
                            "source_citation": 4.5,
                            "evidence_match": 3.5
                        }
                    },
                    "quality": {
                        "overall_score": 3.2,
                        "dimension_scores": {
                            "factual_accuracy": 2.5,
                            "clarity": 3.8,
                            "difficulty": 3.5
                        }
                    }
                },
                "overall_passed": False
            },
            {
                "iteration": 2,
                "critics": {
                    "fact": {
                        "overall_score": 4.8,
                        "dimension_scores": {
                            "source_citation": 4.9,
                            "evidence_match": 4.7
                        }
                    },
                    "quality": {
                        "overall_score": 4.5,
                        "dimension_scores": {
                            "factual_accuracy": 4.8,
                            "clarity": 4.2,
                            "difficulty": 4.5
                        }
                    }
                },
                "overall_passed": True
            }
        ],
        
        # 失敗的改進建議（僅記錄失敗的）✅
        "improvement_history": [
            {
                "iteration": 1,
                "failed": True,
                "failed_critics": ["quality"],
                "failed_criteria": ["factual_accuracy", "clarity"],
                "suggestions": "題目1的答案與證據不符，建議修正...",
                "detailed_feedback": {
                    "per_question": [
                        {
                            "question_index": 1,
                            "issues": ["factual_accuracy"],
                            "suggestions": "答案說「機器學習是...」但證據顯示..."
                        },
                        {
                            "question_index": 3,
                            "issues": ["clarity"],
                            "suggestions": "選項B和D的描述過於相似..."
                        }
                    ]
                }
            }
            // iteration 2 通過了，不記錄
        ]
    },
    
    # === 3. 前端可視化數據 ✅ ===
    "visualization_data": {
        // A. 迭代列表（用於進度條/Timeline）
        "iterations": [
            {
                "number": 1,
                "status": "failed",
                "timestamp": "2025-12-09T15:00:00+08:00",
                "duration_ms": 5000,
                "content_summary": "生成了5題選擇題",
                "improvements_made": null
            },
            {
                "number": 2,
                "status": "passed",
                "timestamp": "2025-12-09T15:01:30+08:00",
                "duration_ms": 3000,
                "content_summary": "改進了2題選擇題（題目1, 3）",
                "improvements_made": [
                    "修正題目1的事實性錯誤",
                    "改進題目3的選項清晰度"
                ]
            }
        ],
        
        // B. 分數趨勢（用於折線圖）
        "score_trends": {
            "overall": [3.2, 4.5],
            "fact": [4.0, 4.8],
            "quality": [3.2, 4.5],
            "factual_accuracy": [2.5, 4.8],
            "clarity": [3.8, 4.2],
            "difficulty": [3.5, 4.5]
        },
        
        // C. 改進的題目高亮（用於UI標示）
        "modified_questions": [1, 3],  // 題目索引
        
        // D. 題目級別的修改詳情
        "modifications": {
            "1": {
                "before": {
                    "question_text": "...",
                    "options": {...}
                },
                "after": {
                    "question_text": "...",
                    "options": {...}
                },
                "reason": "修正事實性錯誤：答案與證據衝突",
                "improved_criteria": ["factual_accuracy"]
            },
            "3": {
                "before": {...},
                "after": {...},
                "reason": "改進清晰度：選項描述過於相似",
                "improved_criteria": ["clarity"]
            }
        }
    },
    
    # === 4. 調試信息（可選）===
    "debug_info": {
        "generation_history": [...],  // 每個版本的完整內容
        "rag_cache_used": true,
        "total_tokens": 12345,
        "total_cost_usd": 0.05,
        "skill_used": "exam_generation_skill",
        "refinement_strategy": "partial"
    }
}
```

---

## 前端可視化支持

### 問題：這些數據都會包含在 API returns 中嗎？

**答案：是的！** ✅ 所有 `visualization_data` 都會包含在 API response 的 `visualization_data` 欄位中。

### 前端如何使用這些數據

#### A. 迭代進度可視化

**使用數據**: `visualization_data.iterations`

**前端實現範例** (React):
```jsx
// Timeline 組件
<Timeline>
  {iterations.map(iter => (
    <Timeline.Item
      key={iter.number}
      color={iter.status === 'passed' ? 'green' : 'red'}
      label={new Date(iter.timestamp).toLocaleTimeString()}
    >
      <h4>第 {iter.number} 次迭代 {iter.status === 'passed' ? '✅' : '❌'}</h4>
      <p>{iter.content_summary}</p>
      {iter.improvements_made && (
        <ul>
          {iter.improvements_made.map((imp, i) => (
            <li key={i}>{imp}</li>
          ))}
        </ul>
      )}
      <small>耗時: {iter.duration_ms}ms</small>
    </Timeline.Item>
  ))}
</Timeline>
```

**UI 效果**:
```
第 1 次迭代 ❌
生成了5題選擇題
耗時: 5000ms
15:00:00

第 2 次迭代 ✅
改進了2題選擇題（題目1, 3）
• 修正題目1的事實性錯誤
• 改進題目3的選項清晰度
耗時: 3000ms
15:01:30
```

#### B. 分數趨勢圖表

**使用數據**: `visualization_data.score_trends`

**前端實現範例** (使用 Chart.js):
```javascript
const chartData = {
  labels: iterations.map(i => `第${i.number}次`),  // ['第1次', '第2次']
  datasets: [
    {
      label: '總分',
      data: score_trends.overall,  // [3.2, 4.5]
      borderColor: 'rgb(75, 192, 192)',
    },
    {
      label: 'Fact Critic',
      data: score_trends.fact,  // [4.0, 4.8]
      borderColor: 'rgb(255, 99, 132)',
    },
    {
      label: 'Quality Critic',
      data: score_trends.quality,  // [3.2, 4.5]
      borderColor: 'rgb(54, 162, 235)',
    }
  ]
};

<Line data={chartData} options={{ ... }} />
```

**UI 效果**: 折線圖顯示分數逐次提升

#### C. 題目高亮顯示

**使用數據**: `visualization_data.modified_questions` 和 `visualization_data.modifications`

**前端實現範例**:
```jsx
{questions.map((q, index) => {
  const isModified = modified_questions.includes(index);
  const modification = modifications[index];
  
  return (
    <QuestionCard
      key={index}
      className={isModified ? 'modified' : ''}
      highlight={isModified}
    >
      {isModified && (
        <Badge color="orange">已改進</Badge>
      )}
      
      <QuestionText>{q.question_text}</QuestionText>
      
      {modification && (
        <ImprovementNote>
          <Icon type="info-circle" />
          改進原因: {modification.reason}
          <br />
          提升維度: {modification.improved_criteria.join(', ')}
        </ImprovementNote>
      )}
    </QuestionCard>
  );
})}
```

**UI 效果**:
- 改進的題目有橘色 badge
- 顯示改進原因和提升的評分維度

#### D. 改進摘要展示

**使用數據**: `critic_summary.improvement_history`

**前端實現範例**:
```jsx
<Collapse>
  {improvement_history.map((hist, i) => (
    <Panel
      key={i}
      header={`第 ${hist.iteration} 次迭代失敗`}
      extra={<Tag color="red">未通過</Tag>}
    >
      <Descriptions bordered size="small">
        <Descriptions.Item label="失敗的 Critics">
          {hist.failed_critics.join(', ')}
        </Descriptions.Item>
        <Descriptions.Item label="失敗的評分維度">
          {hist.failed_criteria.join(', ')}
        </Descriptions.Item>
        <Descriptions.Item label="改進建議" span={3}>
          {hist.suggestions}
        </Descriptions.Item>
      </Descriptions>
      
      <h4>具體問題:</h4>
      <List
        dataSource={hist.detailed_feedback.per_question}
        renderItem={item => (
          <List.Item>
            <strong>題目 {item.question_index}:</strong> {item.suggestions}
          </List.Item>
        )}
      />
    </Panel>
  ))}
</Collapse>
```

---

## 性能優化

### A. RAG 快取實現 ✅

**實現位置**:
1. `retrieve_chunks_node` - 檢查快取
2. `exam_skill_node` / `summarization_skill_node` - 建立和傳遞快取

**效果**:
- 第一次迭代: 正常檢索 RAG（耗時 ~500ms）
- 後續迭代: 使用快取（耗時 ~0ms）
- **節省時間**: (n-1) × 500ms，其中 n = 迭代次數
- **節省成本**: 避免重複的 vector search

### B. 部分重新生成 ✅

**適用範圍**: Exam Generation

**實現**: `_extract_failed_questions` + `_create_refinement_plan`

**效果**:
- 假設5題，2題失敗
- 全部重新生成: 5題 × tokens
- 部分重新生成: 2題 × tokens
- **節省成本**: ~60%

**不適用**: Summary（因為是整體內容）

### C. 並行 Critics（未來優化）

如果啟用多個 critics，可以並行執行：

```python
import asyncio

async def run_critics_node(state):
    tasks = []
    
    if "fact" in enabled_critics:
        tasks.append(run_fact_critic(state))
    if "quality" in enabled_critics:
        tasks.append(run_quality_critic(state))
    
    results = await asyncio.gather(*tasks)
    
    # 合併結果
    critics_results = {
        "fact": results[0] if "fact" in enabled_critics else None,
        "quality": results[1] if "quality" in enabled_critics else None
    }
    # ...
```

**效果**: 節省時間 ~50%（兩個 critic 並行而非串行）

---

## Graph 修改

```python
# graph.py

# 1. Import skill configs
from backend.app.agents.teacher_agent.skills.base import SKILL_CONFIGS

# 2. 更新 node 名稱
builder.add_node("critics", run_critics_node)  # 從 "quality_critic" 改名

# 3. 動態建立 skill → critics edges
build_skill_to_critic_edges(builder, SKILL_CONFIGS)

# 4. 啟用 conditional edge
builder.add_conditional_edges(
    "critics",
    should_continue_from_critic,
    {
        "aggregate_output": "aggregate_output",
        **{
            skill_name: skill_name
            for skill_name, config in SKILL_CONFIGS.items()
            if config.supports_refinement
        }
    }
)
```

---

## 實現步驟

### Phase 1: 基礎 Loop + Skill 架構（優先）

**目標**: 建立基本的迭代循環和可擴充的 skill 架構

1. ✅ 創建 `skills/base.py`，定義 `SkillCapability` 和 `SKILL_CONFIGS`
2. ✅ 實現 `build_skill_to_critic_edges` 函數
3. ✅ 修改 `should_continue_from_critic` 支持動態 skill 檢查
4. ✅ 更新 Graph edges (conditional)
5. ✅ 在 State 中加入所有必要欄位
6. ✅ 重構 `quality_critic_node` → `run_critics_node`
7. ✅ 在 `create_task` 調用時傳遞 `iteration_number`
8. ✅ 測試簡單的 loop (失敗 → 重新生成 → 成功)

**預計時間**: 2-3小時

### Phase 2: RAG 快取

**目標**: 避免重複的 RAG 檢索，提升效率

1. ✅ 在 `retrieve_chunks_node` 加入快取檢查邏輯
2. ✅ 在 skill wrappers 中建立和傳遞快取
3. ✅ 測試快取效果（觀察 log 確認第2次迭代使用快取）

**預計時間**: 1小時

### Phase 3: 統一 Refinement 機制

**目標**: 智能改進，只重新生成失敗的部分

1. ✅ 在 `plan_generation_tasks_node` 加入 refinement 判斷
2. ✅ 實現 helper functions:
   - `_extract_failed_questions`
   - `_find_question_by_index`
   - `_create_refinement_plan`
3. ✅ 在 `_generic_generate_question` 加入 refinement 邏輯
4. ✅ 在 `summarize_node` 加入 refinement 邏輯
5. ✅ 測試部分重新生成（exam）和完整重新生成（summary）

**預計時間**: 2-3小時

### Phase 4: API 輸出優化

**目標**: 完整的 API response，包含前端可視化數據

1. ✅ 在 `aggregate_output_node` 構建完整的 API response
2. ✅ 實現 `visualization_data` 結構:
   - `iterations` 列表
   - `score_trends` 趨勢數據
   - `modified_questions` 高亮信息
   - `modifications` 詳細修改
3. ✅ 實現分數歷史和改進歷史的格式化
4. ✅ 測試 API 輸出格式

**預計時間**: 1-2小時

### Phase 5: Multi-Critic 框架（未來）

**目標**: 支持 Fact Critic

1. ⏳ 實現 `run_fact_critic` 函數
2. ⏳ 更新 `_aggregate_metrics` 支持多 critic
3. ⏳ 測試 Fact + Quality 雙 critic 流程

**預計時間**: 2-3小時（Fact Critic 本身的實現另計）

### Phase 6: 測試與優化

**目標**: E2E 測試，確保功能完整性

1. ✅ E2E 測試場景:
   - 單次通過（生成優質內容）
   - 迭代改進（2-3次迭代後通過）
   - 達到上限（失敗但仍返回結果）
2. ✅ 性能測試:
   - RAG 快取效果
   - 部分重新生成效率
3. ✅ 數據完整性測試:
   - 檢查所有 iteration 正確記錄到資料庫
   - 驗證 parent_task_id 鏈條完整

**預計時間**: 1-2小時

---

## 配置參數

### 環境變數

```bash
# .env
MAX_CRITIC_ITERATIONS=3
CRITIC_MODE=quick  # or comprehensive
ENABLE_QUALITY_CRITIC=true
ENABLE_FACT_CRITIC=false  # 未來啟用
ENABLE_RAG_CACHE=true
ENABLE_PARTIAL_REFINEMENT=true  # 只改進失敗的題目（僅 exam）
```

### API Request 參數

```python
# teacher_testing_router.py

class TestCriticWorkflowRequest(BaseModel):
    unique_content_id: int
    prompt: str
    user_id: int = 1
    
    # Critic 配置
    enabled_critics: List[str] = ["quality"]  # 未來可選 ["fact", "quality"]
    critic_mode: str = "quick"  # "quick" or "comprehensive"
    max_iterations: int = 3
    
    # 調試選項
    debug_mode: bool = False  # 是否返回 debug_info
```

---

## 附錄：關鍵檔案清單

### 新增檔案
- `backend/app/agents/teacher_agent/skills/base.py` - Skill 配置系統

### 修改檔案
- `backend/app/agents/teacher_agent/graph.py` - Multi-critic, conditional edges
- `backend/app/agents/teacher_agent/skills/exam_generator/exam_nodes.py` - Refinement 邏輯
- `backend/app/agents/teacher_agent/skills/summarization/nodes.py` - Refinement 邏輯
- `backend/app/routers/teacher_testing_router.py` - API request/response
- `backend/app/utils/db_logger.py` - iteration_number 傳遞

---


---

**最後更新**: 2025-12-10  
**準備狀態**: ✅ Phase 1 實作中

---

## Phase 1 實現細節 (2025-12-10)

### 目標

實現支持 4 種實驗 workflow 的 Multi-Critic 架構。

### 實驗組別設計

| 實驗組別 | 無 Fact Critic | 有 Fact Critic |
|---------|---------------|---------------|
| **無 Quality Critic** | Workflow 1: Only Generator | Workflow 2: 迭代至 Ragas 指標達標 |
| **有 Quality Critic** | Workflow 3: 迭代至 G-eval 指標達標 | Workflow 4: 迭代至所有指標達標 |

### 資料庫儲存策略

- **不新增**額外的資料庫欄位
- **存入** `ORCHESTRATION_JOBS.experiment_config` (JSONB 欄位)
  ```json
  {
    "enabled_critics": ["fact", "quality"],
    "critic_mode": "quick",
    "max_iterations": 3
  }
  ```
- `workflow_type` 自動判斷：`1_no_critic`, `2_fact_only`, `3_qual_only`, `4_all_critics`

### Critic 回傳格式統一

兩種 critic 都返回統一的 `evaluations` 陣列格式：

```python
{
    "evaluations": [
        {
            "criteria": str,      # "Faithfulness" or "Understandable"
            "analysis": str,      # 分析說明
            "rating": float,      # Ragas: 0.0-1.0, G-eval: 1-5
            "suggestions": List[str]  # 改進建議
        }
    ],
    "is_passed": bool,
    "failed_criteria": List[str]
}
```

### 核心函數

#### 1. `run_fact_critic(state)` - Ragas 評估

- 使用 `CustomFaithfulness` (事實正確性)
- 使用 `CustomAnswerRelevancy` (答案相關性)
- 閾值: 0.7
- 返回統一的 evaluations 格式

#### 2. `run_quality_critic(state)` - G-eval 評估

- 使用現有 `QualityCritic` 類
- 支持 quick/comprehensive 模式
- 5 個評估標準 + Overall Quality

#### 3. `_aggregate_metrics(critics_results)` - 綜合指標

- 合併所有 evaluations 為 `all_evaluations`
- 判斷整體通過/失敗
- 提取所有 failed_criteria
- 合併改進建議

#### 4. `_format_content_for_ragas(content, query, contexts)` - Ragas 格式化

- 將教材內容轉為 Ragas 輸入格式
- 處理 retrieved_text_chunks

#### 5. `run_critics_node(state)` - 主要執行節點

- 依序執行 Fact → Quality
- 構建綜合 feedback
- 更新 feedback history

### 實現檔案

- `backend/app/agents/teacher_agent/graph.py` - Multi-critic helpers + run_critics_node
- `backend/app/routers/teacher_testing_router.py` - API 更新
- `backend/app/utils/db_logger.py` - experiment_config 儲存


---

## Phase 1.5 實現細節 (2025-12-11)

### 目標

重構 Fact Critic 以對齊 Quality Critic 的架構標準，提升一致性與可維護性。

### 核心改進

#### 1. **RAG 資料傳遞優化**
- **問題**：Fact Critic 使用 state 中的 `retrieved_text_chunks`，但這些資料沒有從 subgraph 正確傳遞
- **解決**：在 `exam_skill_node` 和 `summarization_skill_node` 中明確返回 `retrieved_text_chunks` 到 TeacherAgentState
- **效果**：避免 critic 重複檢索，確保使用與 generator 相同的參考資料

#### 2. **LLM 生成 Feedback**
- **問題**：原本使用 hardcoded 的中文模板，缺乏針對性
- **解決**：
  - 新增 `_generate_feedback_with_llm()` 方法，參考 QualityCritic 的 prompt 設計
  - 使用 **Analysis-Rate-Suggest 策略**：先分析 → 再結合 Ragas 分數 → 提供具體建議
  - Prompt 包含 Ragas 原始分數、評估內容、參考資料、評分標準
- **效果**：提供更具體、更有針對性的改進建議

#### 3. **分數標準化 (0-1 → 1-5)**
- **方法**：線性映射 + 四捨五入
  ```python
  raw_score = 1 + (ragas_score × 4)
  normalized_score = round(raw_score)
  ```
- **映射規則**：
  - [0.0, 0.125) → 1
  - [0.125, 0.375) → 2
  - [0.375, 0.625) → 3
  - [0.625, 0.875) → 4
  - [0.875, 1.0] → 5
- **閾值**：4 分以下不通過（對應 Ragas ≥ 0.625）
- **保留資料**：同時保留原始 Ragas 分數和線性映射分數，供後續分析是否需調整為自定義分段

#### 4. **資料庫 Logging 一致性**
- 確保 `fact_critic_node` 和 `quality_critic_node` 的資料庫記錄格式完全一致
- 統一 `feedback` 和 `metrics_detail` 結構
- 所有 LLM 呼叫的 token 使用量與成本記錄到 `agent_tasks` 表

#### 5. **API Response 格式對齊**
- Fact Critic 和 Quality Critic 返回相同的結構：
  ```python
  {
      "evaluations": [
          {
              "criteria": "Faithfulness",
              "analysis": "...",  # LLM 生成
              "rating": 4,        # 整數 1-5
              "suggestions": [...],  # LLM 生成
              "raw_ragas_score": 0.75,  # 保留原始分數
              "raw_linear_score": 4.0   # 保留線性分數
          }
      ],
      "is_passed": bool,
      "failed_criteria": [...]
  }
  ```

### 實現文件

**修改檔案**：
- `backend/app/agents/teacher_agent/critics/fact_critic.py` - 核心重構
- `backend/app/agents/teacher_agent/graph.py` - RAG 傳遞、run_fact_critic
- `backend/app/agents/teacher_agent/state.py` - 確認 retrieved_text_chunks 定義

**新增功能**：
- `normalize_ragas_score()` - 分數標準化函數
- `CustomFaithfulness._generate_feedback_with_llm()` - LLM feedback 生成
- `CustomAnswerRelevancy._generate_feedback_with_llm()` - LLM feedback 生成

### 驗證計劃

1. **Unit Tests**: 測試分數標準化、LLM feedback 生成
2. **Integration Tests**: 測試 RAG caching、資料庫格式一致性
3. **E2E Tests**: 執行 dual-critic workflow，驗證完整流程

### Token 成本估算

- 每次評估增加 2 次 LLM 呼叫（Faithfulness + Relevancy）
- 每次約 500-800 tokens
- 成本增加：~$0.001 USD per iteration (gpt-4o-mini)

---

**最後更新**：2025-12-29  
**實現狀態**：Phase 2 進行中

---

## 變更記錄：2025-12-29 Fact Critic 重構

### 一、移除 Answer Relevancy

#### 移除原因

1. **評估方式不適用於生成任務**
   - Ragas Answer Relevancy 的計算方式是：從答案推斷假設問題，再與原始問題比對 embedding 相似度
   - 這對**知識問答**有效（如「什麼是缺失值？」），但對**任務型指令**無效（如「出兩題選擇題」）
   - 範例：
     - 原始問題：`出兩題資料清理的選擇題`
     - 答案包含兩道選擇題
     - 從答案推斷的假設問題：「處理缺失值的方法？」
     - 假設問題與原始問題語義不相似 → 分數偏低（0.17-0.56）

2. **JSON 解析穩定性問題**
   - Ragas 內部 LLM 呼叫經常返回 markdown 包裹的 JSON（`\`\`\`json...\`\`\``）
   - Ragas 無法解析這種格式，需要額外的 fallback 機制

3. **與 Faithfulness 的職責重疊**
   - Faithfulness 已檢查答案是否基於 context
   - Answer Relevancy 對於 RAG 場景的附加價值有限

#### 移除範圍

- `fact_critic.py`: 刪除 `CustomAnswerRelevancy` class
- `fact_critic.py`: 刪除 `get_fact_critic_embeddings()` function
- `graph.py` / `critics/graph.py`: 移除 Answer Relevancy 相關調用
- `teacher_testing_router.py`: 移除 Answer Relevancy 相關調用
- 相關測試文件

---

### 二、新增 TaskSatisfaction（任務完成度）

#### 設計目的

評估生成結果是否滿足使用者的**基本任務要求**（格式、數量等），取代原本的 Answer Relevancy。

#### 中文名稱

**任務符合度**

#### 評分方式

採用**加權檢查項目**計算 1-5 分，與其他指標（Faithfulness、Quality Metrics）統一評分方式。

#### 檢查項目與權重（exam_generation）

| 檢查項目 | 說明 | 權重 | 理由 |
|---------|------|------|------|
| `question_count` | 題目數量是否符合要求 | 2 | 數量錯誤很明顯 |
| `question_type` | 題型是否符合（選擇題/是非題/問答題） | 2 | 題型錯誤導致不可用 |
| `has_options` | 選擇題是否有 ABCD 選項 | 1 | 選項缺失較易補救 |
| `has_correct_answer` | 是否有正確答案 | 2 | 沒答案無法使用 |
| `has_source` | 是否有來源引用 | 1 | 來源為可選項目 |

**總權重 = 8**

#### 計分公式

```python
weighted_score = sum(check.weight for check in passed_checks)
total_weight = sum(check.weight for check in all_checks)  # = 8

# 線性轉換為 1-5 分
raw_score = 1 + (weighted_score / total_weight) * 4
normalized_score = round(raw_score)
```

#### 分數對應表

| 加權得分 | 比例 | 1-5 分 |
|---------|------|--------|
| 8/8 | 100% | 5 |
| 7/8 | 87.5% | 5 |
| 6/8 | 75% | 4 |
| 5/8 | 62.5% | 4 |
| 4/8 | 50% | 3 |
| 3/8 | 37.5% | 3 |
| 2/8 | 25% | 2 |
| 1/8 | 12.5% | 2 |
| 0/8 | 0% | 1 |

#### 實作方式

使用 **規則檢查 + LLM 輔助** 混合：

1. **規則檢查**（快速、確定性）：
   - 題目數量：解析生成內容中的題目列表
   - 選項存在性：檢查是否有 A/B/C/D 選項
   - 答案存在性：檢查是否有 `correct_answer` 欄位

2. **LLM 輔助檢查**（複雜、彈性）：
   - 從 user_query 解析要求的題目數量和題型
   - 對題型進行語義匹配

#### 輸出格式

```python
{
    "score": 0.875,              # 原始比例 (0-1)
    "normalized_score": 5,       # 標準化分數 (1-5)
    "checks": [
        {"name": "question_count", "weight": 2, "passed": True, "expected": 2, "actual": 2},
        {"name": "question_type", "weight": 2, "passed": True, "expected": "multiple_choice", "actual": "multiple_choice"},
        {"name": "has_options", "weight": 1, "passed": True},
        {"name": "has_correct_answer", "weight": 2, "passed": True},
        {"name": "has_source", "weight": 1, "passed": False}
    ],
    "weighted_score": 7,
    "total_weight": 8,
    "analysis": "生成結果符合要求，僅缺少來源引用。",
    "suggestions": ["建議為每道題目加入來源頁碼引用。"]
}
```

#### 修改檔案

- `backend/app/agents/teacher_agent/critics/fact_critic.py`: 
  - 移除 `CustomAnswerRelevancy`
  - 新增 `TaskSatisfaction` class
- `backend/app/agents/teacher_agent/critics/graph.py`: 將 `answer_relevancy` 替換為 `task_satisfaction`
- `backend/app/routers/teacher_testing_router.py`: 更新 debug API
- 相關測試文件

---

### 三、更新後的 Fact Critic 架構

```
Fact Critic
├── Faithfulness (Ragas + LLM Feedback, 1-5 分)
│   → 答案是否基於 context，沒有捏造
│
└── TaskSatisfaction (Rule + LLM, 1-5 分) ← 新增
    → 生成結果是否符合任務要求（題數、題型、格式）
```

#### 執行順序

```
1. Faithfulness 評估（1-5 分）
2. TaskSatisfaction 評估（1-5 分）
3. Quality Critic 評估（1-5 分 × N 個指標）
```

> TaskSatisfaction 與其他指標同等對待，統一輸出 1-5 分。

---

### 四、保留項目（未來可用）

- **Context Precision**（主題相關性）：評估檢索到的 context 是否與 user query 相關
  - 目前暫不實作，因使用者 query 不一定明確指定單元
  - 預留介面，未來可加入
