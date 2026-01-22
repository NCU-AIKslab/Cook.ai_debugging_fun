# 2025-11-26 工作日誌：Quality Critic 整合與日誌優化

## ✅ 已完成項目 (Completed)

### 1. 核心功能整合
- [x] **Quality Critic Node 實作**：成功將 `quality_critic_node` 整合至 Teacher Agent Graph，支援異步執行 (Async)。
- [x] **通用評估測試**：修改 E2E API，確認 Summary (摘要) 內容可被通用 Critic 正確評估。
- [x] **題號格式確認**：確認保留 `question_type` + `question_number` 格式，無需重新編號。

### 2. 系統架構優化
- [x] **Async/Sync 支援**：升級 `log_task` decorator，同時支援同步與異步函數的自動日誌記錄。
- [x] **Graph Invocation**：將 API Server 的調用方式改為 `await ainvoke` 以支援異步節點。
- [x] **State 管理**：在 `TeacherAgentState` 中新增 `critic_passed` 與 `critic_metrics` 欄位，確保評估結果正確傳遞。

### 3. 資料庫與日誌 (Logging) 改進
- [x] **日誌標準化**：將 `critic_db_utils.py`, `graph.py`, `db_logger.py` 中的 `print` 全部替換為標準 `logging`。
- [x] **資料庫記錄修復**：
    - 解決 `quality_critic` agent name 重複問題 (區分為 `quality_critic` 與 `quality_critic_db`)。
    - 修正 Task Description 為英文。
    - 移除硬編碼的 Model Name。
- [x] **除錯追蹤**：在 `create_task` 中加入 `parent_task_id` 的日誌記錄以利除錯。

## 📋 待辦事項 (Todo)

### 1. 流程控制與重試
- [ ] **QA Critic 串接**：將 `qa_critic` 正確串接到 Graph 中。
- [ ] **重試機制 (Retry Logic)**：實作 `revise_node` 與條件邊界，確保當評估 Failed 時觸發重新生成。
- [ ] **Parent Task ID 修復**：持續排查並修復部分 Agent (如 `exam_generation_skill`) 遺漏 `parent_task_id` 的問題。

### 2. Critic 優化
- [ ] **Fact Critic 調整**：參考現有的 `quality_critic` 架構來調整 `fact_critic`。
