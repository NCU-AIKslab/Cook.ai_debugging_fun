# 2024-12-10 Critic Architecture Refactor

## 工作摘要
重构 Critic 架构，将单一 orchestrator 拆分为独立的 `fact_critic` 和 `quality_critic` nodes，修复 iteration 控制和数据库日志问题。

## 完成的工作

### 1. Critic 节点拆分
- ✅ 创建独立的 `fact_critic_node` 和 `quality_critic_node`
  - 每个 critic 有自己的 `@log_task` decorator
  - 各自创建独立的 task record
- ✅ 移除旧的 `run_critics_node` orchestrator
- ✅ 删除冗余的 `quality_critic_db` task

**文件修改**: `backend/app/agents/teacher_agent/graph.py`

### 2. 数据库日志优化
- ✅ 创建新函数 `save_critic_evaluation_to_db`
  - 只创建 `task_evaluations` 记录
  - 不创建冗余的 `agent_tasks`
  - 引用 critic node 自己的 task_id
- ✅ 正确追踪 `evaluation_stage`: 1 (fact), 2 (quality)
- ✅ 修复 `iteration_number` 追踪

**文件修改**: `backend/app/agents/teacher_agent/critics/critic_db_utils.py`

### 3. Graph 路由更新
- ✅ 修改 `build_skill_to_critic_edges` 支持动态路由
  - 根据 `enabled_critics` 选择第一个 critic
  - 支持 fact only、quality only 或 both
- ✅ 添加 `route_after_fact_critic` 处理 fact→quality 路由
- ✅ 更新 `should_continue_from_critic` 聚合两个 critics 的结果

**文件修改**: `backend/app/agents/teacher_agent/graph.py`

### 4. Iteration 控制修复
**问题**: `iteration_count` 一直停留在 1，导致无限循环

**根本原因**:
- Generator 检查不存在的 `critic_feedback` 字段
- 应检查 `fact_passed`/`quality_passed`

**解决方案**:
```python
has_critic_result = state.get("fact_passed") is not None or state.get("quality_passed") is not None
next_iteration = current_iteration + 1 if has_critic_result else current_iteration
```

**文件修改**: `backend/app/agents/teacher_agent/graph.py` (exam_skill_node, summarization_skill_node)

### 5. 评估数据完整性
- ✅ 修复 critic nodes 返回完整的 `feedback` 和 `metrics`
- ✅ 返回格式:
  ```json
  {
    "fact_feedback": {"evaluations": [...]},
    "fact_metrics": {
      "overall_passed": bool,
      "scores": {"Faithfulness": 0.85, ...}
    }
  }
  ```

**文件修改**: `backend/app/agents/teacher_agent/graph.py`

### 6. 子任务 Iteration 传播
**问题**: Subgraph 子任务（retriever, plan_generation_tasks 等）的 `iteration_number` 都是 1

**根本原因**: `iteration_count` 递增发生在调用 subgraph **之后**

**解决方案**: 将递增移到调用 subgraph **之前**
```python
# BEFORE calling subgraph
next_iteration = current_iteration + 1 if has_critic_result else current_iteration
skill_input = {"iteration_count": next_iteration}
final_skill_state = exam_generator_app.invoke(skill_input)
```

**文件修改**: `backend/app/agents/teacher_agent/graph.py`

### 7. State 定义更新
- ✅ 添加新字段到 `TeacherAgentState`:
  - `fact_passed`, `fact_feedback`, `fact_metrics`, `fact_failed_criteria`
  - `quality_passed`, `quality_feedback`, `quality_metrics`, `quality_failed_criteria`
- ✅ 保留旧字段 `critic_passed` 用于向后兼容

**文件修改**: `backend/app/agents/teacher_agent/state.py`

## 测试验证

### 测试配置
- Max Iterations: 2
- Enabled Critics: fact, quality
- Content: 2 multiple-choice questions

### 验证结果
✅ **Iteration 控制**: 正确在 iteration=2 时终止
✅ **数据库记录**: 每个 critic 有独立的 task 和 evaluation 记录
✅ **Iteration 追踪**: 所有任务正确标记 iteration_number
✅ **评估数据**: 返回完整的 scores 和 feedback

### 数据库结构
```
agent_tasks:
  - exam_skill_router (iter=1)
  - fact_critic (iter=1)
  - quality_critic (iter=1)
  - exam_skill_router (iter=2)
  - retriever (iter=2) ✓ Fixed
  - plan_generation_tasks (iter=2) ✓ Fixed
  - fact_critic (iter=2)
  - quality_critic (iter=2)

task_evaluations:
  - task_id=fact_critic_1, stage=1, iter=1
  - task_id=quality_critic_1, stage=2, iter=1
  - task_id=fact_critic_2, stage=1, iter=2
  - task_id=quality_critic_2, stage=2, iter=2
```

## 待办事项

### 高优先级
- [ ] 测试 fact only 和 quality only 模式
- [ ] 验证 summarization workflow 的 critic 流程
- [ ] 检查 comprehensive mode 的 critic 评估

### 中优先级
- [ ] 优化 critic feedback 的显示格式
- [ ] 添加 critic 评估结果的聚合统计
- [ ] 考虑添加 critic 评估的缓存机制（避免重复评估相同内容）

### 低优先级
- [ ] 重构 critic 配置为统一的配置类
- [ ] 添加 critic 评估的详细时间追踪
- [ ] 考虑支持自定义 critic threshold

## 技术债务
- 移除所有被标记为 "Deprecated" 的字段（在确认没有依赖后）
- 统一 critic 评估结果的数据格式（目前 fact 和 quality 格式略有不同）

## 影响范围
- ✅ **无破坏性变更**: 保留了向后兼容的字段
- ✅ **数据库兼容**: 新增字段，未删除旧字段
- ✅ **API 兼容**: 外部接口未改变

## 相关文件
- `backend/app/agents/teacher_agent/graph.py` - 主要重构
- `backend/app/agents/teacher_agent/critics/critic_db_utils.py` - 数据库日志
- `backend/app/agents/teacher_agent/state.py` - State 定义
- `backend/app/utils/db_logger.py` - 日志工具（清理 debug logs）

## Commit Message
```
Refactor critic architecture into separate fact/quality nodes with fixed iteration control and database logging
```
