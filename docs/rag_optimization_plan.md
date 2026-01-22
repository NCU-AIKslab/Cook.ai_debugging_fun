# RAG 優化計畫 v2.0（多模態優先）

## 當前架構總覽

### 支援的檔案格式 ✅
已實作的 Loaders：
- ✅ **PDF** ([`pdf_loader.py`](file:///home/monica/Cook.ai/backend/app/services/document_loader/pdf_loader.py)) - pdfplumber + OCR
- ✅ **PPTX** ([`pptx_loader.py`](file:///home/monica/Cook.ai/backend/app/services/document_loader/pptx_loader.py)) - python-pptx + OCR
- ✅ **DOCX** ([`docx_loader.py`](file:///home/monica/Cook.ai/backend/app/services/document_loader/docx_loader.py))
- ✅ **TXT** ([`txt_loader.py`](file:///home/monica/Cook.ai/backend/app/services/document_loader/txt_loader.py))
- ✅ **Image** ([`image_loader.py`](file:///home/monica/Cook.ai/backend/app/services/document_loader/image_loader.py)) - jpg/png/gif/bmp/tiff/webp
- ✅ **Web** ([`web_loader.py`](file:///home/monica/Cook.ai/backend/app/services/document_loader/web_loader.py))
- ✅ **Google Drive** ([`google_drive_loader.py`](file:///home/monica/Cook.ai/backend/app/services/document_loader/google_drive_loader.py))

### 多模態資料結構

**Page.structured_elements 格式**：
```python
[
    {
                parts.append("[圖片]")
    return " ".join(parts).strip()
```

---

## 優化計畫（按您建議的順序）

### 🎯 **Phase 1: 擴充檔案格式支援**

#### 目標
確保所有 loader 都已整合到 ingestion pipeline

#### 檢查清單

| Loader | 已實作 | 已整合 | 測試狀態 |
|--------|-------|-------|---------|
| PDF | ✅ | ✅ | ✅ |
| PPTX | ✅ | ✅ | ✅ |
| DOCX | ✅ | ❓ | ❓ |
| TXT | ✅ | ❓ | ❓ |
| Image | ✅ | ❓ | ❓ |
| Web | ✅ | ❓ | ❓ |
| Google Drive | ✅ | ❓ | ❓ |

#### 實作步驟

1. **測試所有 loaders**
   ```python
   # backend/tests/test_all_loaders.py
   
   def test_docx_loader():
       loader = get_loader("sample.docx")
       doc = loader.load("test_files/sample.docx")
       assert len(doc.pages) > 0
       assert doc.pages[0].structured_elements
   
   def test_image_loader():
       loader = get_loader("sample.png")
       doc = loader.load("test_files/sample.png")
       # 確認 OCR 有運作
       assert doc.pages[0].structured_elements[0].get("ocr_text")
   ```

2. **修復任何問題**
   - DOCX/Web/Google Drive 是否缺少 `structured_elements`？
   - 確保所有 loader 返回統一格式

3. **在 `ingestion.py` 中測試**
   ```bash
   python -m backend.app.agents.teacher_agent.ingestion
   # 測試各種檔案格式
   ```

---

### 🎯 **Phase 2: 優化 OCR 與文字轉錄**

#### 當前 OCR 設定
```python
# ocr_utils.py:15
pytesseract.image_to_string(image, lang='chi_tra+eng')
```

#### 優化方向

##### 2.1 改用更準確的 OCR 引擎

**選項 A：PaddleOCR**（推薦，中文辨識更佳）
```python
# backend/app/services/document_loader/ocr_utils.py

from paddleocr import PaddleOCR

# 初始化（全域單例）
ocr_engine = PaddleOCR(use_angle_cls=True, lang='ch', use_gpu=False)

def ocr_image_to_text_paddle(image_bytes: bytes) -> str:
    """使用 PaddleOCR 辨識圖片文字"""
    try:
        image = Image.open(io.BytesIO(image_bytes))
        result = ocr_engine.ocr(np.array(image), cls=True)
        
        # 提取文字
        texts = []
        for line in result[0]:
            texts.append(line[1][0])  # 每一行的文字
        
        return "\n".join(texts)
    except Exception as e:
        print(f"PaddleOCR error: {e}")
        # Fallback to Tesseract
        return ocr_image_to_text_tesseract(image_bytes)
```

**選項 B：Azure/Google Vision API**（付費，最準確）
```python
from google.cloud import vision

client = vision.ImageAnnotatorClient()

def ocr_image_to_text_google(image_bytes: bytes) -> str:
    image = vision.Image(content=image_bytes)
    response = client.text_detection(image=image)
    return response.full_text_annotation.text
```

##### 2.2 圖片前處理（提升 OCR 準確度）

```python
def preprocess_image_for_ocr(image_bytes: bytes) -> bytes:
    """
    OCR 前處理：灰階、去噪、二值化
    """
    import cv2
    import numpy as np
    
    # 載入圖片
    nparr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    # 1. 轉灰階
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # 2. 去噪
    denoised = cv2.fastNlMeansDenoising(gray)
    
    # 3. 二值化（閾值自動調整）
    binary = cv2.adaptiveThreshold(
        denoised, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
        cv2.THRESH_BINARY, 11, 2
    )
    
    # 轉回 bytes
    _, buffer = cv2.imencode('.png', binary)
    return buffer.tobytes()
```

##### 2.3 OCR 錯誤修正

```python
import re

OCR_CORRECTION_DICT = {
    r'PREROCESSING': 'PREPROCESSING',
    r'DEATIE\s+DIEANIN': '',
    r'DATO': 'DATA',
    r'(\d)\s+(\d)': r'\1\2',  # 修正數字間多餘空格
}

def post_process_ocr_text(text: str) -> str:
    """OCR 後處理：修正常見錯誤"""
    for pattern, repl in OCR_CORRECTION_DICT.items():
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    return text.strip()
```

---

### 🎯 **Phase 3: 資料清理（保留 base64）** ⭐⭐⭐⭐⭐ 最關鍵

> [!IMPORTANT]
> **Phase 1 與 Phase 3 合併實作**
> 
> 原因：需要先統一 loader 格式（Phase 1），才能正確清理與保留多模態資料（Phase 3）

#### 核心設計：雙軌資料儲存

**目標**：
- ✅ **Chunk 文字** (`chunk_text`): 用於 text embedding 和檢索
- ✅ **Multimodal metadata** (`multimodal_metadata`): 保留 base64 供多模態 LLM 使用

#### 資料庫架構理解

| 表名 | 儲存層級 | 資料內容 | 用途 |
|------|----------|----------|------|
| **document_content** | Page | `structured_content` (完整 base64) | 供 Generator 使用完整頁面資料 |
| **document_chunks** | Chunk | `chunk_text` (文字+OCR) + `embedding` + **`multimodal_metadata`** (新增) | 向量檢索 + 圖片資訊保留 |

#### 實作檢查清單

##### 3.1 資料庫準備
- [ ] 建立 migration script: `migrations/add_multimodal_metadata.sql`
  ```sql
  ALTER TABLE document_chunks ADD COLUMN multimodal_metadata JSONB;
  CREATE INDEX idx_chunks_multimodal ON document_chunks USING GIN (multimodal_metadata);
  ```
- [ ] 執行資料庫 migration
- [ ] 驗證欄位新增成功

##### 3.2 統一 Document Loaders
- [ ] 修改 `__init__.py` - 簡化 Page dataclass
  - 移除 `native_text`, `extracted_images`, `generated_text_for_chunking`
  - 只保留 `page_number` 和 `structured_elements`
  - 移除 `ExtractedImage` dataclass
- [ ] 修改 PPTX Loader - 使用 `structured_elements`
- [ ] 修改 DOCX Loader - 使用 `structured_elements`
- [ ] 修改 TXT Loader - 使用 `structured_elements`
- [ ] 修改 Image Loader - 使用 `structured_elements`
- [ ] 修改 Web Loader - 完全重構使用 `structured_elements` + OCR
- [ ] 優化 PDF Loader - 簡化 `top` 欄位處理

**統一格式**:
```python
structured_elements = [
    {"type": "text", "content": "段落文字..."},
    {"type": "image", "base64": "data:image/png;base64,...", "ocr_text": "..."},
]
```

##### 3.3 Ingestion Pipeline 改造

**刪除舊函數**:
- [ ] 刪除 `_generate_human_text_from_structured_content` (line 29-44)
  - **舊功能**: 只提取文字和 OCR，丟棄 base64
  - **問題**: 無清理、無多模態保留

**實作新函數**:
- [ ] 實作 `_clean_and_prepare_multimodal_content`
  - **新功能**: 清理 + 保留 base64 + 返回雙軌資料
  - **返回**: `(text_for_chunking, multimodal_metadata)`
  
- [ ] 實作 `_is_code_block` - 程式碼檢測
  - 檢測 `import`, `def`, `class` 等關鍵字
  - 過濾程式碼區塊，不納入 chunk
  
- [ ] 實作 `_clean_text` - 文字清理
  - 移除頁碼（單獨的數字行）
  - 移除教師資訊
  - 標準化空白符號
  
- [ ] 實作 `_post_process_ocr` - OCR 後處理
  - 移除 OCR 噪音字元
  - 修正數字間多餘空格

**修改 ingestion 流程**:
- [ ] 修改 Task 4 (Save Document Content) - 使用新的清理函數
  ```python
  text_for_chunking, mm_metadata = _clean_and_prepare_multimodal_content(
      page.structured_elements
  )
  page.text_for_chunking = text_for_chunking
  page.multimodal_metadata = mm_metadata
  ```

- [ ] 修改 Task 6 (Generate Embeddings) - 儲存 `multimodal_metadata`
  ```python
  chunk_data = [{
      "chunk_text": text,
      "metadata": meta,
      "multimodal_metadata": mm_meta,  # ✅ 新增
      "embedding": embedding
  }...]
  ```

##### 3.4 Text Splitter 升級

- [ ] 修改 `chunk_document` 函數簽名
  - 返回三元組: `(chunk_text, page_metadata, multimodal_metadata)`
  
- [ ] 實作字元到圖片的映射邏輯
  - 建立 `char_to_image_map` 追蹤圖片位置
  
- [ ] 實作 chunk-level 圖片分配
  - 根據 chunk 的字元範圍，分配屬於該 chunk 的圖片
  - 構建每個 chunk 的 `multimodal_metadata`

##### 3.5 RAG Agent 整合

- [ ] 修改 `rag_agent.py` - search() 方法
  ```python
  SELECT id, chunk_text, metadata, multimodal_metadata  -- ✅ 新增
  FROM document_chunks
  ```

- [ ] 修改返回格式
  ```python
  found_text_chunks.append({
      "chunk_id": chunk_id,
      "text": chunk_text,
      "source_pages": page_numbers,
      "multimodal_metadata": mm_meta  # ✅ 新增
  })
  ```

#### multimodal_metadata 格式

```json
{
  "images": [
    {
      "position": 0,
      "base64": "data:image/png;base64,...",
      "ocr_text": "優點：易於實作、計算速度快"
    }
  ],
  "contains_code": false
}
```

#### 資料流程

```
Loader → structured_elements (text + image base64)
    ↓
_clean_and_prepare_multimodal_content()
    ↓
├─ text_for_chunking: "文字 + [圖片內容: 清理後的OCR]"
└─ multimodal_metadata: {"images": [{"base64": "...", "ocr_text": "..."}]}
    ↓
document_content.structured_content ✅ 保留完整 base64
document_chunks.chunk_text + multimodal_metadata ✅ 雙軌儲存
    ↓
RAG 檢索 → text_chunks (含 multimodal_metadata)
         → page_content (含完整 structured_elements)
    ↓
Generator: 使用 page_content (完整 base64) → GPT-4V 看圖
Ragas: 使用 text_chunks.text (純文字+OCR) → 文字比對
```

---

#### 驗證檢查清單

- [ ] 測試所有 7 種檔案格式 ingest (PDF, PPTX, DOCX, TXT, PNG, Web, Google Drive)
- [ ] 驗證 `document_content.structured_content` 保留完整 base64
- [ ] 驗證 `document_chunks.multimodal_metadata` 正確儲存
- [ ] 驗證 `chunk_text` 乾淨（無程式碼、無頁碼、OCR 已清理）
- [ ] 端到端 RAG 流程測試

**SQL 驗證範例**:
```sql
-- 檢查 document_content
SELECT structured_content -> 0 FROM document_content LIMIT 1;
-- 預期: {"type": "image", "base64": "data:image/png;base64,...", "ocr_text": "..."}

-- 檢查 document_chunks
SELECT multimodal_metadata FROM document_chunks LIMIT 1;
-- 預期: {"images": [...], "contains_code": false}
```

---

### 🎯 **Phase 0: Debug API 建立** ⭐⭐⭐⭐⭐（當前優先）

#### 目標
建立專門的 Debug API 來可視化和驗證多模態 RAG 系統

#### 背景
- Vision LLM 已整合（12/17 完成）
- multimodal_metadata 已加入 ingestion pipeline
- 需要工具來驗證整個流程是否正確運作

#### 實作內容

##### 0.1 創建 RAG Debug Router

**新增檔案**: `backend/app/routers/rag_debug_router.py`

**端點 1: `/debug/rag_retrieval`**
- 功能: 測試 RAG 檢索流程
- 返回:
  - 原始 `chunks`（含 `multimodal_metadata`）
  - 原始 `page_content`（完整結構化內容）
  - LLM 輸入格式（text + base64 images）
  - 人類可讀格式（純文字）
  - 執行時間統計

**端點 2: `/debug/rag_full_pipeline`**
- 功能: 完整 RAG 流程測試（檢索 + 生成 + Ragas 準備）
- 返回:
  - 檢索結果
  - LLM 生成答案（使用 base64 圖片）
  - Ragas 評估輸入（純文字）
  - 執行時間統計

##### 0.2 關鍵設計原則

**資料分離策略**:
```
RAG 檢索
    ↓
┌─────────────────┬────────────────────┐
│ chunks          │ page_content       │
│ (輕量文字)       │ (完整結構化內容)    │
└─────────────────┴────────────────────┘
         ↓                    ↓
    給 Ragas         給 LLM (_prepare_multimodal_content)
    (純文字)         (提取 base64 + 文字)
```

**LLM 多模態支援** ✅:
- 模型: `gpt-4o-mini` / `gpt-4o`
- 函數: `_prepare_multimodal_content()` (exam_nodes.py Line 97-127)
- 輸入: `page_content` → 輸出: (text, [base64_images])

##### 0.3 驗證目標

- [ ] Vision LLM 描述出現在 `chunks[].text` 中
- [ ] `multimodal_metadata` 正確儲存在資料庫
- [ ] LLM 確實接收到 base64 圖片
- [ ] Ragas 只接收純文字（不含 base64）
- [ ] 執行時間合理（檢索 < 200ms，完整流程 < 5s）

##### 0.4 工作量與時程

- **實作時間**: 1-1.5 小時
- **測試時間**: 30 分鐘
- **預期完成**: 當日

---

### 🎯 **Phase 4: 語義邊界切分**

#### 4.1 按段落切分

```python
def semantic_chunk_by_paragraphs(
    pages: List[Page],
    max_chunk_size: int = 1000,
    min_chunk_size: int = 200
) -> List[Tuple[str, Dict, Dict]]:
    """
    基於段落的語義切分
    """
    chunks = []
    
    for page in pages:
        # 提取文字元素
        text_elements = [
            e for e in page.structured_elements 
            if e["type"] == "text"
        ]
        
        # 合併小段落
        paragraphs = []
        current_para = ""
        
        for elem in text_elements:
            content = elem["content"]
            
            # 段落結束標記：換行或句號
            if content.endswith(('\n', '。', '！', '？')):
                current_para += content
                paragraphs.append(current_para.strip())
                current_para = ""
            else:
                current_para += content + " "
        
        if current_para:
            paragraphs.append(current_para.strip())
        
        # 組合段落成 chunks
        current_chunk_elements = []
        current_length = 0
        
        for para in paragraphs:
            if current_length + len(para) > max_chunk_size:
                # 當前 chunk 完成
                if current_length >= min_chunk_size:
                    text, mm_meta = clean_and_structure_chunk(
                        "\n\n".join(current_chunk_elements),
                        page.structured_elements,
                        0, 0  # 需調整為實際範圍
                    )
                    chunks.append((
                        text,
                        {"page_numbers": [page.page_number]},
                        mm_meta
                    ))
                
                current_chunk_elements = [para]
                current_length = len(para)
            else:
                current_chunk_elements.append(para)
                current_length += len(para)
        
        # 最後一個 chunk
        if current_chunk_elements and current_length >= min_chunk_size:
            text, mm_meta = clean_and_structure_chunk(...)
            chunks.append((text, {...}, mm_meta))
    
    return chunks
```

---

### 🎯 **Phase 5: 檢索優化**

#### 5.1 Hybrid Search（向量 + 關鍵字）

```python
# rag_agent.py

def hybrid_search(
    self,
    user_prompt: str,
    unique_content_id: int,
    top_k: int = 3,
    alpha: float = 0.7
) -> Dict:
    """混合檢索：向量 + 全文檢索"""
    
    # 1. 向量檢索
    vector_results = self._vector_search(
        user_prompt, unique_content_id, top_k * 2
    )
    
    # 2. PostgreSQL 全文檢索
    keyword_results = self._fulltext_search(
        user_prompt, unique_content_id, top_k * 2
    )
    
    # 3. 合併分數
    combined = self._merge_scores(
        vector_results, keyword_results, alpha
    )
    
    # 4. 取 top-k 並補充 multimodal_metadata
    top_chunks = combined[:top_k]
    
    # 5. 為每個 chunk 補充圖片資訊
    enhanced_chunks = []
    for chunk in top_chunks:
        multimodal_meta = chunk.get('multimodal_metadata', {})
        enhanced_chunks.append({
            "chunk_id": chunk['chunk_id'],
            "text": multimodal_meta.get('text_only', chunk['text']),
            "images": multimodal_meta.get('images', []),
            "source_pages": chunk['source_pages']
        })
    
    return {
        "text_chunks": enhanced_chunks,
        "page_content": self._get_page_content(...)
    }
```

#### 5.2 建立全文檢索索引

```sql
-- 為 chunk_text 建立 tsvector 索引
ALTER TABLE document_chunks 
ADD COLUMN search_vector tsvector
GENERATED ALWAYS AS (
    to_tsvector('simple', coalesce(chunk_text, ''))
) STORED;

CREATE INDEX idx_chunks_search 
ON document_chunks USING GIN(search_vector);
```

---

## 實作優先級與預期效果

| Phase | 項目 | 工作量 | 預期效果 |
|-------|------|--------|----------|
| 1 | 檔案格式測試 | 2-3 小時 | 確保所有格式可用 |
| 2 | OCR 優化 | 4-5 小時 | ⭐⭐⭐⭐ 辨識準確度 +30% |
| 3 | 資料清理 + 多模態保留 | 5-6 小時 | ⭐⭐⭐⭐⭐ **關鍵改進** |
| 4 | 語義切分 | 3-4 小時 | ⭐⭐⭐⭐ Chunk 品質提升 |
| 5 | Hybrid Search | 4-5 小時 | ⭐⭐⭐⭐ 檢索準確度 +25% |

## 預期成果

### 資料品質
- ✅ OCR 準確度：70% → **90%+**
- ✅ Chunk 清潔度：包含程式碼噪音 → **純概念文字**
- ✅ 多模態保留：圖片遺失 → **完整保留 base64**

### 檢索與評估
- ✅ Faithfulness: 0.18 → **0.6-0.8**
- ✅ Answer Relevancy: 0.32 → **0.7-0.9**
- ✅ 檢索準確度：提升 **40%+**

### 多模態 LLM 支援
- ✅ GPT-4V/Claude 3 可直接讀取圖片
- ✅ 更精準的視覺資訊理解
- ✅ 減少 LLM 幻覺（有圖為證）
