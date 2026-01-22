# 2026-01-05 工作紀錄：課程內容導向之前端頁面設計與對應資料庫架構重構與遷移

本日主要完成了課程核心架構的資料庫重構，實現了資源與應用層的分離，並統一了教材與作業的管理模式。

## 1. 主要目標
- **[前端]** 全新美術設計：採用 Gamma 風格，建立現代化 Design System。
- **[前端]** 優化教師端 UX：移除側邊欄，採用沉浸式全螢幕佈局。
- **[資料庫]** 優化 `course_units` 表結構。
- **[資料庫]** 建立作業 (`assignments`) 管理機制。
- **[資料庫]** 重構教材 (`materials`) 架構，實現資源重用。
- **[資料庫]** 補足公告 (`announcements`) 功能。
- **[資料庫]** 清理冗餘表結構與命名一致性。

## 2. 前端設計與優化 (Frontend Design & UX)

### A. 設計系統 (Design System)
- 建立了全新的 [`design_system.md`](file:///home/monica/.gemini/antigravity/brain/8edd7743-7dab-4fe6-abdd-eb72a3d0921e/design_system.md)。
- **風格定位**：Gamma 風格 (現代、卡片式、玻璃擬態)。
- **核心色票**：定義了 Primary (紫色系), Secondary, Surface, Text 等語意化變數。
- **元件庫**：統一了 Button, Card, Input, Badge 的樣式標準。

### B. 介面佈局優化
- **教師端課程頁面 (`TeacherCourseDetail`)**：
  - **移除側邊欄**：改為頂部導航與全寬內容區，提供更開闊的操作視野。
  - **Grid 佈局**：採用 Masonry 或 Grid 排列章節卡片，提升視覺層次。
  - **互動優化**：新增章節 (Add Chapter) Modal 介面更新，支援章節編號、名稱與說明。
  - **文案調整**：將「章節數」修正為「章節編號」。

## 3. 執行的 Migration 變更

本日共產生並執行了以下 Alembic Migrations：

### A. `f1a2b3c4d5e6_add_topic_id_to_course_units.py`
- **目的**：更新章節表以符合新需求。
- **變更**：
  - `week` → 改名為 `topic_id`。
  - `chapter_name` → 改名為 `name`。
  - 新增 `description` 欄位。
  - 移除 `display_order`。
  - 嘗試移除 `semester_name` (確認資料庫中已不存在)。

### B. `h3i4j5k6l7m8_create_assignments_tables.py`
- **目的**：建立作業管理系統。
- **變更**：
  - 建立 `assignments` 表。
  - 採用多態關聯 (`source_type`, `source_id`) 指向內容來源，避免資料冗餘。
  - 建立 `submissions` 與 `submission_attachments` 表。

### C. `i4j5k6l7m8n9_refactor_materials_to_uploaded_contents.py`
- **目的**：重構資源架構，分離「資源池」與「應用層」。
- **變更**：
  - `materials` 表 → 改名為 `uploaded_contents` (作為全域資源池)。
  - 移除 `uploaded_contents` 中的 `course_unit_id` FK (解除章節綁定)。
  - 新建立 `course_materials` 表 (應用層)，負責管理章節教材的顯示與排序。

### D. `j5k6l7m8n9o0_cleanup_and_finalize_course_schema.py`
- **目的**：最終清理與命名統一。
- **變更**：
  - `assignments` → 改名為 `course_assignments` (與 `course_materials` 對稱)。
  - 刪除 `assignment_attachments` (確認因多態設計而冗餘)。
  - 新增 `course_announcements` 表 (補足缺漏功能)。
  - 保留 `submission_attachments`。

### E. 刪除
- 刪除了 `g2h3i4j5k6l7_add_indexes_to_course_content_map.py`，因為 `course_content_map` 的功能已被 `course_materials` 與 `course_assignments` 取代。

## 4. 最終資料庫架構層級

### 資源池層 (Resource Pool) - 僅存儲實體內容
- **`uploaded_contents`**: 所有上傳的檔案 (PDF, DOCX 等)。
- **`generated_contents`**: 所有 AI 生成的內容。

### 應用層 (Application Layer) - 管理課程結構
- **`course_units`**: 課程章節。
- **`course_materials`**: 章節教材 (引用資源池)。
- **`course_assignments`**: 章節作業 (引用資源池)。
- **`course_announcements`**: 課程公告。
- **`submissions`**: 學生作業繳交。

## 5. 文件更新
- 更新了 `docs/db_schema.md` 以反映最新的資料庫結構。
- 更新了 `walkthrough.md` 記錄遷移流程。

## 6. 待辦事項/備註
- 前端 `TeacherCourseDetail` 需對接新的 `course_materials` 與 `course_assignments` API。
- 需開發 `course_announcements` 的前端介面。
