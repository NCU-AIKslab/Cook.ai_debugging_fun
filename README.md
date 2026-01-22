# Cook.ai

## Project Overview

This project, `Cook.ai`, appears to be a web application for educational purposes, with separate portals for teachers and students.

*   **Backend:** The backend is a Python Flask application that serves a REST API. It seems to be in the early stages of development, with a placeholder endpoint for generating course materials.
*   **Frontend:** The frontend is a React application built with Vite. It provides the user interface for the teacher and student portals.

## Building and Running

### Backend

1.  **Navigate to the project directory:**
    ```bash
    cd Cook.ai
    ```

2.  **Create and activate a virtual environment:**
    ```bash
    python -m venv venv
    source venv/bin/activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r backend/requirements.txt
    ```

4.  **Run the backend server:**
    ```bash
    python backend/app.py
    ```
    The backend will be running on `http://127.0.0.1:5001`.

### Frontend

1.  **Navigate to the frontend directory:**
    ```bash
    cd Cook.ai/frontend
    ```

2.  **Install dependencies:**
    ```bash
    npm install
    ```

3.  **Run the frontend development server:**
    ```bash
    npm run dev
    ```
    The frontend will be accessible at `http://localhost:5173` (or another port if 5173 is in use).

## Development Conventions

*   **Backend:** The backend follows a modular structure using Flask Blueprints. The code is organized into `teacher`, `student`, and `coding` modules, although only the `teacher` module has a defined route so far.
*   **Frontend:** The frontend uses React with functional components and hooks. The code is structured into `pages` and `components` directories, with routing handled by `react-router-dom`. The project is set up with ESLint for code linting.

### Backend Task Logging (`@log_task` Decorator)

為了確保後端 Agent 的所有任務執行過程都能被詳細記錄，我們使用了一個強大的 `@log_task` 裝飾器。這個裝飾器自動處理了任務的建立、狀態更新、執行時間、LLM token 用量及成本等日誌記錄環節，極大地簡化了 Agent 節點的程式碼。

**裝飾器定義**：`backend/app/utils/db_logger.py`

**使用方式**：

將 `@log_task` 裝飾器應用於任何 LangGraph 節點函式上。

```python
from backend.app.utils.db_logger import log_task

@log_task(
    agent_name="your_agent_name",
    task_description="A brief description of what this task does.",
    input_extractor=lambda state: {"key_input_1": state.get("value_1"), "key_input_2": state.get("value_2")}
)
def your_node_function(state: YourAgentState) -> dict:
    # ... 節點的核心業務邏輯 ...
    result = {"some_output_key": "some_value"}

    # 如果節點內部有 LLM 呼叫，請確保回傳以下 metrics
    # prompt_tokens = ...
    # completion_tokens = ...
    # estimated_cost_usd = ...

    return {
        **result, # 節點的實際輸出
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "estimated_cost_usd": estimated_cost_usd
    }
```

**參數說明**：

*   `agent_name` (str)：該任務所屬的 Agent 或節點的名稱 (例如 `"agent_router"`, `"retriever"`, `"plan_generation_tasks"`)。
*   `task_description` (str)：該任務的簡要描述。
*   `input_extractor` (Optional[callable])：一個可選的函式，它接受 `state` 字典作為輸入，並回傳一個字典，該字典將被記錄為該任務的 `task_input`。
    *   **目的**：確保每個任務的輸入日誌都是相關且有意義的。
    *   **範例**：`lambda state: {"user_query": state.get("user_query"), "document_id": state.get("unique_content_id")}`
    *   如果未提供，預設會記錄 `{"user_query": state.get("user_query")}`。

**自動處理的日誌環節**：

*   **任務建立**：在節點函式執行前，自動在 `agent_tasks` 資料表中建立一筆新的任務記錄，狀態為 `in_progress`。
*   **狀態管理**：
    *   將當前任務的 `task_id` 注入 `state` 為 `current_task_id`，供節點內部使用（例如，子圖可以將其作為 `parent_task_id`）。
    *   將當前任務的 `task_id` 注入 `state` 為 `parent_task_id`，供圖中**下一個**節點使用。
*   **任務更新**：
    *   **成功**：節點函式執行成功後，自動將任務狀態更新為 `completed`，並記錄函式的回傳值作為 `output`。
    *   **失敗**：節點函式拋出異常或回傳的字典中包含 `"error"` 鍵時，自動將任務狀態更新為 `failed`，並記錄錯誤訊息。
*   **性能指標**：自動記錄任務的執行時間 (`duration_ms`)。
*   **LLM Metrics**：如果節點函式回傳的字典中包含 `prompt_tokens`、`completion_tokens` 和 `estimated_cost_usd`，裝飾器會自動將這些 LLM 相關的指標記錄到資料庫中。

**節點函式要求**：

*   節點函式應回傳一個字典。
*   如果節點內部有 LLM 呼叫，請確保在回傳的字典中包含 `prompt_tokens`、`completion_tokens` 和 `estimated_cost_usd` 鍵，以便裝飾器能正確記錄這些指標。
*   如果節點執行失敗，可以回傳 `{"error": "錯誤訊息"}`，裝飾器會自動將任務標記為 `failed`。

---

## Document Loaders and Supported Formats

本專案的後端具備強大的文件載入器 (Document Loaders) 功能，能夠從多種來源和格式提取文字內容及圖片，並將其標準化為 `Document` 物件，以便傳遞給 LLM 進行處理。

### 核心設計理念

*   **統一輸出**：所有 Loader 都會輸出一個統一的 `Document` 物件，包含 `content` (文字內容) 和 `images` (Base64 編碼的圖片 URI 列表)。
*   **多模態支援**：提取的文字和圖片會一起傳遞給支援多模態的 LLM，賦予 LLM 視覺能力。
*   **OCR 整合**：對於圖片中的文字，會自動進行 OCR (光學字元辨識) 提取，並將其整合到 `content` 中，同時註明來源。

### 支援的資料來源與格式

*   **上傳文件 (Upload Files)**
    *   `.txt`：直接讀取文字內容。
    *   `.pdf`：使用 `pypdf` 套件提取文字和圖片。圖片會進行 OCR 提取文字。
    *   `.docx`：使用 `python-docx` 套件提取文字和圖片。圖片會進行 OCR 提取文字。
    *   `.pptx`：使用 `python-pptx` 套件提取文字和圖片。圖片會進行 OCR 提取文字。
    *   **圖片檔案** (`.jpg`, `.jpeg`, `.png`, `.gif`, `.bmp`, `.tiff`, `.webp`)：
        *   使用 `PIL` 套件讀取圖片。
        *   **OCR 提取文字**：使用 `pytesseract` 套件提取圖片中的文字，並將其註明後整合到 `content` 中。
        *   **Base64 編碼**：將圖片轉換為 Base64 編碼，作為 `images` 傳遞給 LLM。
*   **從網站導入 (Website)**
    *   **文字內容**：使用 `langchain-community` 中的 `WebBaseLoader` 套件，可以高效抓取網頁的主要文字內容。
    *   **圖片部分**：`WebBaseLoader` 不會自動抓取圖片。因此，會另外使用 `BeautifulSoup4` 爬蟲抓取 HTML 中的 `<img>` 資訊，並發送 HTTP 請求下載圖片的二進位資料，然後進行 Base64 編碼和 OCR 處理。
*   **Google Drive 雲端硬碟**
    *   **認證**：使用 `google-api-python-client` 和 `google-auth-oauthlib` 進行 Google 帳戶認證 (OAuth 2.0)。
    *   **檔案下載**：透過 Google Drive API 下載指定檔案的內容。
    *   **後續處理**：下載的檔案會根據其類型（例如 PDF, DOCX, 圖片等）自動交由對應的本地 Loader 進行文字和圖片提取。

### Generated Content Storage Conventions

為了方便前端渲染和統一資料結構，所有儲存在 `generated_contents` 資料表 `content` 欄位 (JSONB 類型) 中的最終產出，都將自動包含一個 `type` 鍵。這個 `type` 鍵的值與 `content_type` 欄位的值一致，是前端判斷如何渲染內容的重要依據。

**範例**：

*   **聊天訊息 (text_message)**：
    ```json
    {
      "type": "message",
      "content": "您好！我是一位 AI 教學助理..."
    }
    ```
*   **總結報告 (summary_report)**：
    ```json
    {
      "type": "summary",
      "main_title": "資料前處理概述",
      "sections": [
        {"title": "定義", "content_list": ["資料前處理是...", "旨在將原始數據轉換成..."]},
        // ...
      ]
    }
    ```
*   **考卷題目 (exam_questions)**：
    ```json
    {
      "type": "exam_questions",
      "questions": [
        {"question_number": 1, "question_text": "...", "options": {...}, "correct_answer": "...", "source": {...}},
        // ...
      ]
    }
    ```

## Future Enhancements

## Future Enhancements

以下是未來可以考慮擴展的功能：

*   **更多文件格式支援**：
    *   **試算表檔案** (`.xlsx`, `.csv`)：提取表格數據。
    *   **電子郵件檔案** (`.eml`, `.msg`)：提取郵件內容及附件。
*   **OCR 提取文字優化**：目前 OCR 提取的文字精準度有待提升，未來可考慮：
    *   優化圖片預處理 (例如去噪、增強對比)。
    *   使用更進階的 OCR 引擎或雲端 OCR 服務。
    *   針對特定語言或字體進行模型微調。
*   **Agent 提示詞優化**：提升 Agent 生成教材的品質和相關性。
*   **前端介面整合**：為文件上傳、網頁導入和 Google Drive 檔案選擇提供友善的使用者介面 (例如 Google Drive File Picker)。

## Testing Document Loaders and Agents

您可以透過執行 `backend/run_server.py` 腳本來測試文件載入器和教材生成 Agent 的功能。

1.  **確保環境準備就緒**：
    *   已安裝 `backend/requirements.txt` 中的所有依賴。
    *   已安裝 Tesseract OCR 引擎 (並安裝了 `chi_tra` 語言包，如果需要中文識別)。
    *   已將 Google Cloud Console 下載的 `credentials.json` 檔案放置在 `backend` 目錄中。
    *   已將您的 Google 帳戶新增為 Google Cloud 專案的「測試使用者」。

2.  **執行測試腳本**：
    ```bash
    python3 backend/run_server.py
    ```

3.  **選擇測試模式**：
    程式會顯示一個菜單，您可以選擇：
    *   `1. Document Loader Test`：測試單個檔案或 URL 的讀取功能。
    *   `2. Agent Material Generation Test`：測試 Agent 的教材生成功能 (需要設定 `OPENAI_API_KEY` 環境變數)。
    *   `3. Google Drive Loader Test`：測試 Google Drive 檔案的讀取功能 (首次執行需進行瀏覽器認證)。
    *   `q. Quit`：退出測試。

請根據提示輸入您想測試的檔案路徑、URL 或 Google Drive 檔案 ID。
