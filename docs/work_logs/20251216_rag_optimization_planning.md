# Work Log - 2025-12-16

## Critic 開發收斂與 RAG 優化規劃

---

## 📌 **主要成果**

### 1. Critic 開發階段性收斂

#### 完成項目
- ✅ **Quality Critic RAG 資料流對齊**
  - 修改 `run_quality_critic` 使用 `state.retrieved_text_chunks` 而非資料庫查詢
  - 解決跨迭代資料累積問題（Iteration 1: 3 chunks, Iteration 2: 6 chunks → 統一為 3 chunks）
  - 新增 debug logging 與 Fact Critic 一致

- ✅ **Ragas 計算函數驗證**
  - 驗證 `normalize_ragas_score()` 線性映射邏輯正確
  - 確認 `CustomFaithfulness` 和 `CustomAnswerRelevancy` 分數計算
  - 修復 `raw_linear_score` 精度問題（移除 `round(, 2)`，保留完整精度）
  - 驗證端到端計算鏈路

- ✅ **API 簡化與統一輸出**
  - 簡化 `test_critic_workflow` API 文檔（移除範例請求、詳細說明）
  - 修改返回格式：所有 4 種 workflow 統一輸出 critic 評估結果，不輸出題目
  - 返回結構包含 `fact_critic` 和 `quality_critic` 完整評估資訊

#### 文檔產出
- ✅ [`walkthrough.md`](file:///home/monica/.gemini/antigravity/brain/f8063e97-141e-4c0f-a519-d59973014320/walkthrough.md) - Fact Critic 重構總結
  - 6 大改進項目
  - 測試結果分析
  - 真實品質問題診斷（Generator 幻覺、OCR 錯誤）

#### Commit
```
Align QualityCritic RAG data flow with FactCritic, remove DB query, and add unified tracing for both critics
```

---

### 2. RAG 優化規劃（新分支：feat/rag-fact-optimise）

#### 程式碼架構分析

**已分析的核心檔案**：
- [`rag_agent.py`](file:///home/monica/Cook.ai/backend/app/agents/rag_agent.py) - Vector search with pgvector
- [`embedding_service.py`](file:///home/monica/Cook.ai/backend/app/services/embedding_service.py) - OpenAI text-embedding-3-small
- [`text_splitter.py`](file:///home/monica/Cook.ai/backend/app/services/text_splitter.py) - 固定長度切分（1000 chars）
- [`ingestion.py`](file:///home/monica/Cook.ai/backend/app/agents/teacher_agent/ingestion.py) - 文件進檔流程
- **Document Loaders**（7 種格式）：
  - PDF, PPTX, DOCX, TXT, Image, Web, Google Drive
  - OCR: Tesseract (chi_tra+eng)
  - 圖片處理：base64 URI + OCR text

#### 關鍵發現

**🔴 核心問題：多模態資料損失**

`_generate_human_text_from_structured_content` 將圖片 base64 URI 丟棄：
```python
elif item.get("type") == "image":
    parts.append(f"[圖片: {ocr_text}]")  # ❌ base64 遺失
```

**其他問題**：
1. **Chunk 品質差**：OCR 錯誤、程式碼噪音未過濾
2. **檢索不準確**：純向量搜尋，無 reranking
3. **切分策略差**：固定長度切斷語義
4. ~~Embedding 快取~~：已有文件 hash 機制，query embedding 快取效益低

#### 優化計畫（5 階段）

詳見 [`docs/rag_optimization_plan.md`](file:///home/monica/Cook.ai/docs/rag_optimization_plan.md)

| Phase | 項目 | 工作量 | 核心改進 |
|-------|------|--------|----------|
| 1 | 檔案格式測試與整合 | 2-3h | 確保所有 loader 可用 |
| 2 | OCR 優化 | 4-5h | PaddleOCR + 圖片前處理 + 錯誤修正 |
| 3 | **資料清理 + 多模態保留** | 5-6h | ⭐ **雙軌儲存：text_only + base64** |
| 4 | 語義邊界切分 | 3-4h | 按段落/主題切分 |
| 5 | Hybrid Search | 4-5h | 向量 + 全文檢索 |

**Phase 3 核心設計**：
```sql
ALTER TABLE document_chunks 
ADD COLUMN multimodal_metadata JSONB;
-- {
--   "images": [{"base64": "...", "ocr_text": "..."}],
--   "text_only": "純文字（用於 embedding）",
--   "chunk_type": "concept" / "code_example"
-- }
```

#### 預期成果
- OCR 準確度：70% → **90%+**
- Faithfulness: 0.18 → **0.6-0.8**
- Answer Relevancy: 0.32 → **0.7-0.9**
- 支援多模態 LLM（GPT-4V/Claude 3）

---

## 🔧 **程式碼修改**

### Fact Critic 精度修復
- [`fact_critic.py`](file:///home/monica/Cook.ai/backend/app/agents/teacher_agent/critics/fact_critic.py#L178)
  - 移除 `round(raw_linear_score, 2)`，保留完整精度
  - Faithfulness 和 Answer Relevancy 都套用

### Quality Critic 資料流對齊
- [`graph.py`](file:///home/monica/Cook.ai/backend/app/agents/teacher_agent/graph.py#L521-L541)
  - 改用 `state.get("retrieved_text_chunks", [])` 而非 `get_rag_chunks_by_job_id()`
  - 新增格式轉換邏輯（`source_pages` 欄位）
  - 新增 debug logging

### API 簡化
- [`teacher_testing_router.py`](file:///home/monica/Cook.ai/backend/app/routers/teacher_testing_router.py#L48-L69)
  - 簡化 docstring（移除範例）
  - 修改返回格式為 critic 評估結果

---

## 📊 **Ragas 計算驗證報告**

**驗證項目**：
- ✅ `normalize_ragas_score()` - 線性映射 + 四捨五入
- ✅ 閾值設定：4 分（Ragas ≥ 0.625）
- ✅ `CustomFaithfulness` 分數計算
- ✅ `CustomAnswerRelevancy` 分數計算
- ✅ `run_fact_critic` 評估流程
- ✅ 端到端數據流

**驗證案例**：
```
Input:  ragas_score = 0.1121341025744007
Output: raw_linear_score = 1.4485364102976028  ✅
        normalized_score = 1
```

---

## 📝 **決策記錄**

### 決策 1：移除 Query Embedding Cache
**原因**：
- 已有文件級別 hash 快取（避免重複處理文件）
- 已有 Session 級別快取（`state.rag_cache`）
- Query 很少完全重複
- 單一 query embedding 成本極低（$0.000001）

**結論**：不實作 Redis embedding cache，專注於更有價值的優化（資料清理、Hybrid Search）

### 決策 2：優化順序調整
**調整**：
- 原計畫：Debug API → 資料清理 → 語義切分 → Cache → Hybrid Search
- 新計畫：檔案格式 → **OCR 優化** → **資料清理+多模態** → 語義切分 → Hybrid Search

**原因**：
- 使用者需求：從源頭改善資料品質
- 多模態保留是關鍵功能（未來支援 GPT-4V）

---

## 🎯 **下一步行動**

1. **Phase 1**：測試所有檔案格式 loader（DOCX/Web/Google Drive）
2. **Phase 2**：整合 PaddleOCR 或 Google Vision API
3. **Phase 3**：實作雙軌資料儲存（重點）
4. 建立 Debug API（垂直切片可視化）
5. 執行端到端測試並調整優化參數

---

## 📚 **參考文件**

- [RAG Optimization Plan](file:///home/monica/Cook.ai/docs/rag_optimization_plan.md)
- [Fact Critic Walkthrough](file:///home/monica/.gemini/antigravity/brain/f8063e97-141e-4c0f-a519-d59973014320/walkthrough.md)
- [Critic Plan](file:///home/monica/Cook.ai/docs/critic_plan.md)

---

**日期**：2025-12-16  
**分支**：`feat/rag-fact-optimise`  
**狀態**：Critic 開發收斂完成，RAG 優化規劃完成，準備實作
