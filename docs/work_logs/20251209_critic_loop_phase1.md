# 工作日誌 - 2025-12-09

> **主題**: Critic Loop Phase 1 實現 + Model Name Logging 修復

---

## 📋 今日完成項目

### 1. ✅ Model Name Logging 修復

**問題**: `agent_tasks` 表中的 `model_name` 欄位為 NULL

**解決方案**:
- 修改 `db_logger.py`:
  - 在 `update_task()` 新增 `model_name` 參數
  - Async/Sync wrapper 都提取並傳遞 `model_name`
- 修改所有使用 LLM 的 nodes，在 return 中加入 `model_name`:
  - `router_node` (graph.py)
  - `plan_generation_tasks_node` (exam_nodes.py)
  - `_generic_generate_question` (exam_nodes.py)
  - `summarize_node` (summarization/nodes.py)
  - `general_chat_node` (general_chat/nodes.py)

**驗證**: ✅ 資料庫正確記錄 model_name (如 "gpt-4o-mini")

---

### 2. ✅ Critic Loop - Phase 1: 基礎 Loop + Skill 架構

#### 2.1 ✅ Skill Configuration System

**新增檔案**: `backend/app/agents/teacher_agent/skills/base.py`

```python
class SkillCapability(BaseModel):
    name: str
    supports_refinement: bool
    supports_critic: bool
    refinement_strategy: Literal["partial", "full", "none"]

SKILL_CONFIGS = {
    "exam_generation_skill": SkillCapability(...),
    "summarization_skill": SkillCapability(...),
    "general_chat_skill": SkillCapability(...)
}
```

**優點**:
- 集中管理 skill 特性
- 易於擴展新 skills
- 動態建構 graph edges

#### 2.2 ✅ Graph Infrastructure 更新

**檔案**: `backend/app/agents/teacher_agent/graph.py`

**新增功能**:
1. **Dynamic Edge Construction**:
   ```python
   def build_skill_to_critic_edges(builder, skill_configs):
       # 根據 skill config 自動建立 edges
       # exam/summary → critics
       # general_chat → aggregate_output (bypass)
   ```

2. **Updated Conditional Edge**:
   ```python
   def should_continue_from_critic(state):
       # 動態檢查 skill 是否支持 refinement
       # 自動增加 iteration_count
       # 判斷是否 loop back
   ```

3. **Conditional Edges for Loop**:
   ```python
   builder.add_conditional_edges(
       "critics",
       should_continue_from_critic,
       {
           "aggregate_output": "aggregate_output",
           "exam_generation_skill": "exam_generation_skill",
           "summarization_skill": "summarization_skill"
       }
   )
   ```

#### 2.3 ✅ State Management

**檔案**: `backend/app/agents/teacher_agent/state.py`

**新增欄位**:
```python
class TeacherAgentState(TypedDict):
    # Critic 配置
    enabled_critics: List[str]
    critic_mode: str
    
    # 迭代管理
    iteration_count: int
    max_iterations: int
    
    # Critic Feedback
    critic_feedback: List[Dict[str, Any]]
    critic_passed: Optional[bool]
    critic_metrics: Optional[Dict[str, Any]]
    
    # 版本追蹤
    generation_history: List[Dict]
    
    # RAG 快取
    rag_cache: Optional[Dict]
```

#### 2.4 ✅ Database Logging 改進

**檔案**: `backend/app/utils/db_logger.py`

**修改**: 
- Async/Sync wrappers 都在 `create_task()` 時傳遞 `iteration_number`:
  ```python
  iteration_number=state.get("iteration_count", 1)
  ```

#### 2.5 ✅ Node Refactoring

**檔案**: `backend/app/agents/teacher_agent/graph.py`

**變更**:
- 重命名: `quality_critic_node` → `run_critics_node`
- 更新所有 graph builder 引用
- 準備 multi-critic 架構

#### 2.6 ✅ 功能驗證

**測試結果** (用戶確認):
- ✅ Iteration 1: 生成 → Critic 失敗 → Loop back
- ✅ Iteration 2: 重新生成 → Critic 通過 → 結束
- ✅ 資料庫正確記錄 `iteration_number`
- ✅ `parent_task_id` 鏈條完整

---

## 📌 明日待辦事項

### Priority 1: Multi-Critic Framework 完成

#### ⬜ 1.1 API Input 支持 Critic 選擇

**目標**: 讓使用者在 API request 中選擇要啟用哪些 critics

**修改檔案**: `backend/app/routers/teacher_testing_router.py`

```python
class TestCriticWorkflowRequest(BaseModel):
    unique_content_id: int
    prompt: str
    user_id: int = 1
    
    # 新增欄位 ⬜
    enabled_critics: List[str] = ["quality"]  # ["quality"], ["fact"], ["fact", "quality"]
    critic_mode: str = "quick"  # "quick" or "comprehensive"
    max_iterations: int = 3
```

**修改檔案**: `backend/app/routers/teacher_testing_router.py` (endpoint)

```python
@router.post("/test_critic_workflow")
async def test_critic_workflow(request: TestCriticWorkflowRequest):
    initial_state = {
        # ... 現有欄位 ...
        "enabled_critics": request.enabled_critics,  # ⬜ 新增
        "critic_mode": request.critic_mode,  # ⬜ 新增
        "max_iterations": request.max_iterations
    }
```

#### ⬜ 1.2 實現 Multi-Critic Helper Functions

**檔案**: `backend/app/agents/teacher_agent/graph.py`

**新增函數**:

```python
# ⬜ 待實現
async def run_quality_critic(state: TeacherAgentState) -> dict:
    """
    從現有的 run_critics_node 邏輯中抽取
    
    Returns:
        {
            "is_passed": bool,
            "scores": {...},
            "feedback": {...},
            "failed_criteria": [...]
        }
    """
    pass

# ⬜ 待實現
async def run_fact_critic(state: TeacherAgentState) -> dict:
    """
    使用 fact_critic.py 的 CustomFaithfulness 和 CustomAnswerRelevancy
    
    Returns:
        {
            "is_passed": bool,
            "scores": {...},
            "feedback": {...},
            "factual_errors": [...]
        }
    """
    pass

# ⬜ 待實現
def _aggregate_metrics(critics_results: Dict) -> dict:
    """
    綜合多個 critic 的指標
    
    Returns:
        {
            "is_passed": bool,
            "failed_critics": ["quality"],
            "failed_criteria": [...],
            "overall_scores": {...},
            "improvement_suggestions": "..."
        }
    """
    pass
```

#### ⬜ 1.3 重構 run_critics_node

**檔案**: `backend/app/agents/teacher_agent/graph.py`

**修改**: 使用 helper functions 實現 multi-critic 執行

```python
async def run_critics_node(state: TeacherAgentState) -> dict:
    enabled_critics = state.get("enabled_critics", ["quality"])
    critics_results = {}
    overall_passed = True
    
    # 1. 執行 Fact Critic (優先)
    if "fact" in enabled_critics:
        fact_result = await run_fact_critic(state)
        critics_results["fact"] = fact_result
        if not fact_result.get("is_passed"):
            overall_passed = False
    
    # 2. 執行 Quality Critic
    if "quality" in enabled_critics:
        quality_result = await run_quality_critic(state)
        critics_results["quality"] = quality_result
        if not quality_result.get("is_passed"):
            overall_passed = False
    
    # 3. 構建綜合 feedback
    combined_feedback = {
        "iteration": state.get("iteration_count", 1),
        "critics": critics_results,
        "overall_passed": overall_passed,
        "timestamp": datetime.now(TAIPEI_TZ).isoformat()
    }
    
    # 4. 更新 feedback history
    feedback_history = state.get("critic_feedback", [])
    feedback_history.append(combined_feedback)
    
    return {
        "critic_passed": overall_passed,
        "critic_feedback": feedback_history,
        "critic_metrics": _aggregate_metrics(critics_results)
    }
```

---

### Priority 2: Phase 2 - RAG 快取

#### ⬜ 2.1 Retrieve Chunks Node 快取檢查

**檔案**: `backend/app/agents/teacher_agent/skills/exam_generator/exam_nodes.py`

```python
@log_task(...)
def retrieve_chunks_node(state: ExamGenerationState) -> dict:
    # 檢查是否使用快取 ⬜
    if state.get("use_cached_rag") and state.get("cached_rag_data"):
        logger.info("📦 Using cached RAG results")
        cached_data = state["cached_rag_data"]
        return {
            "retrieved_text_chunks": cached_data["text_chunks"],
            "retrieved_page_content": cached_data["page_content"],
            # ...
        }
    
    # 正常檢索
    rag_results = rag_agent.search(...)
    # ...
```

#### ⬜ 2.2 Skill Wrappers 建立快取

**檔案**: `backend/app/agents/teacher_agent/graph.py`

```python
@log_task(...)
def exam_skill_node(state: TeacherAgentState) -> dict:
    iteration = state.get("iteration_count", 1)
    
    skill_input = {...}
    
    # RAG 快取 ⬜
    if iteration > 1 and state.get("rag_cache"):
        skill_input["use_cached_rag"] = True
        skill_input["cached_rag_data"] = state["rag_cache"]
    
    final_skill_state = exam_generator_app.invoke(skill_input)
    
    # 建立 RAG 快取（第一次迭代）⬜
    rag_cache = state.get("rag_cache")
    if not rag_cache and final_skill_state.get("retrieved_text_chunks"):
        rag_cache = {
            "text_chunks": final_skill_state["retrieved_text_chunks"],
            "page_content": final_skill_state["retrieved_page_content"],
            "cached_at": datetime.now(TAIPEI_TZ).isoformat()
        }
    
    return {
        # ...
        "rag_cache": rag_cache
    }
```

**同樣修改**: `summarization_skill_node`

---

### Priority 3: Phase 3 - Refinement 機制

#### ⬜ 3.1 Exam Generation Refinement

**檔案**: `backend/app/agents/teacher_agent/skills/exam_generator/exam_nodes.py`

##### ⬜ 3.1.1 Plan Generation with Refinement

```python
def plan_generation_tasks_node(state: ExamGenerationState) -> dict:
    # === Refinement Mode === ⬜
    if state.get("is_refinement"):
        feedback = state.get("refinement_feedback", {})
        previous_content = state.get("previous_content", [])
        
        # 解析 feedback，找出需要改進的題目
        failed_questions = _extract_failed_questions(feedback, previous_content)
        
        if not failed_questions:
            # 全部重新生成
            return _create_initial_plan(state["query"], state)
        
        # 只重新生成失敗的題目 ✅
        refinement_plan = _create_refinement_plan(
            failed_questions=failed_questions,
            feedback=feedback
        )
        
        return {
            "generation_plan": refinement_plan,
            # ...
        }
    
    # === Initial Generation Mode ===
    else:
        return _create_initial_plan(state["query"], state)
```

##### ⬜ 3.1.2 Helper Functions

```python
# ⬜ 待實現
def _extract_failed_questions(feedback: Dict, previous_content: List) -> List[Dict]:
    """從 feedback 中提取需要改進的題目"""
    pass

# ⬜ 待實現
def _create_refinement_plan(failed_questions: List, feedback: Dict) -> List[Dict]:
    """為失敗的題目創建改進計劃"""
    pass

# ⬜ 待實現
def _find_question_by_index(index: int, content: List) -> Dict:
    """從內容中找出指定索引的題目"""
    pass
```

##### ⬜ 3.1.3 Generation with Refinement

```python
def _generic_generate_question(state: ExamGenerationState, task_type_name: str) -> dict:
    current_task = state.get("current_task", {})
    
    # === Refinement Mode === ⬜
    if current_task.get("type", "").startswith("refine_"):
        questions_to_refine = current_task.get("questions_to_refine", [])
        feedback_summary = current_task.get("feedback_summary", "")
        
        # 構建 refinement prompt
        # 呼叫 LLM 改進
        # ...
        
        return {
            "final_generated_content": refined_content,
            # ...
        }
    
    # === Initial Generation Mode ===
    else:
        # 現有邏輯
        pass
```

#### ⬜ 3.2 Summarization Refinement

**檔案**: `backend/app/agents/teacher_agent/skills/summarization/nodes.py`

```python
def summarize_node(state: SummarizationState) -> dict:
    # === Refinement Mode === ⬜
    if state.get("is_refinement"):
        feedback = state.get("refinement_feedback", {})
        previous_summary = state.get("previous_content")
        
        # 構建 refinement prompt（包含之前的摘要和 feedback）
        # 呼叫 LLM 完整重新生成
        # ...
        
        return {
            "final_generated_content": refined_summary,
            # ...
        }
    
    # === Initial Generation Mode ===
    else:
        # 現有邏輯
        pass
```

#### ⬜ 3.3 Skill Wrappers 傳遞 Refinement Context

**檔案**: `backend/app/agents/teacher_agent/graph.py`

```python
def exam_skill_node(state: TeacherAgentState) -> dict:
    iteration = state.get("iteration_count", 1)
    is_refinement = iteration > 1
    
    skill_input = {
        # ... 現有欄位 ...
        "is_refinement": is_refinement,  # ⬜
        "iteration_count": iteration
    }
    
    # 如果是 refinement，傳遞 feedback 和 previous content ⬜
    if is_refinement:
        latest_feedback = state.get("critic_feedback", [])[-1]
        skill_input["refinement_feedback"] = latest_feedback
        
        history = state.get("generation_history", [])
        if history:
            skill_input["previous_content"] = history[-1]["content"]
    
    # ...
    
    # 記錄到 generation_history ⬜
    history = state.get("generation_history", [])
    history.append({
        "iteration": iteration,
        "content": generated_content,
        "task_id": state.get("current_task_id"),
        "timestamp": datetime.now(TAIPEI_TZ).isoformat()
    })
    
    return {
        # ...
        "generation_history": history
    }
```

---

### Priority 4: Phase 4 - API 輸出優化

#### ⬜ 4.1 Aggregate Output Node 改進

**檔案**: `backend/app/agents/teacher_agent/graph.py`

```python
def aggregate_output_node(state: TeacherAgentState) -> dict:
    # ... 現有邏輯 ...
    
    # 構建完整的 API response ⬜
    return {
        "job_id": job_id,
        "status": "completed",  # or "partial_success"
        
        # 最終結果
        "final_result": {
            "content": [...],
            "title": "...",
            "display_type": "...",
            "iteration": state.get("iteration_count", 1)
        },
        
        # Critic 摘要 ⬜
        "critic_summary": {
            "total_iterations": state.get("iteration_count", 1),
            "final_passed": state.get("critic_passed"),
            "enabled_critics": state.get("enabled_critics", []),
            "scores_history": [...],
            "improvement_history": [...]
        },
        
        # 前端可視化數據 ⬜
        "visualization_data": {
            "iterations": [...],
            "score_trends": {...},
            "modified_questions": [...],
            "modifications": {...}
        }
    }
```

---

## 📊 整體進度

### Phase 1: 基礎 Loop + Skill 架構 ✅ [100%]
- [x] Skill Configuration System
- [x] Graph Infrastructure
- [x] State Management
- [x] Database Logging
- [x] Basic Loop Testing

### Phase 2: RAG 快取 ⬜ [0%]
- [ ] Retrieve chunks 快取檢查
- [ ] Skill wrappers 建立快取
- [ ] 測試快取效果

### Phase 3: Refinement 機制 ⬜ [0%]
- [ ] Exam generation refinement
- [ ] Summarization refinement
- [ ] Skill wrappers 傳遞 context
- [ ] Helper functions
- [ ] 測試部分/完整重新生成

### Phase 4: API 輸出優化 ⬜ [0%]
- [ ] Aggregate output 改進
- [ ] Visualization data 結構
- [ ] 測試 API 輸出

### Phase 5: Multi-Critic 完整實現 ⬜ [0%]
- [ ] API input 支持 critic 選擇 ⭐ **Priority 1**
- [ ] run_quality_critic helper ⭐ **Priority 1**
- [ ] run_fact_critic helper ⭐ **Priority 1**
- [ ] _aggregate_metrics helper ⭐ **Priority 1**
- [ ] 重構 run_critics_node ⭐ **Priority 1**
- [ ] 測試 dual critic flow

### Phase 6: 測試與優化 ⬜ [0%]
- [ ] E2E 測試
- [ ] 性能測試
- [ ] 數據完整性測試

---

## 📝 重要筆記

### 設計決策

1. **Skill Config 系統**: 使用集中配置管理 skill 特性，易於擴展
2. **Dynamic Edges**: 根據配置自動建立 graph edges，減少硬編碼
3. **Critic 執行順序**: Fact → Quality（事實正確性優先）
4. **Refinement 策略**: 
   - Exam: 部分重新生成（只改失敗題目）
   - Summary: 完整重新生成（整體內容）

### 已知問題

1. ⚠️ `db_logger.py:29`: "Did not recognize type 'vector'" - 可忽略（pgvector 警告）
2. ✅ pycache 問題: 重命名 node 後需清除 pycache

### 測試要點

- 基本 loop 已驗證 ✅
- Multi-critic 尚未整合（明日 Priority 1）
- RAG 快取、Refinement 尚未實現

---

## 🔗 相關文件

- 實現計劃: `docs/work_logs/critic_plan.md`
- Skill 配置: `backend/app/agents/teacher_agent/skills/base.py`
- 主要 Graph: `backend/app/agents/teacher_agent/graph.py`
- State 定義: `backend/app/agents/teacher_agent/state.py`
