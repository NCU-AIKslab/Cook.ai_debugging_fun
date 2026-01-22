"""
Orchestrator for handling the ingestion of documents into the system.
"""
import hashlib
import time
import os
from typing import Dict, Any, List, Tuple, Optional

from sqlalchemy import create_engine, MetaData, Table, select, insert, update, delete
from pgvector.sqlalchemy import Vector

from backend.app.utils import db_logger

# --- Database Setup ---
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set.")

engine = create_engine(DATABASE_URL)
metadata = MetaData()

# Reflect tables used in this orchestrator
unique_contents = Table('unique_contents', metadata, autoload_with=engine)
uploaded_contents = Table('uploaded_contents', metadata, autoload_with=engine)
document_content = Table('document_content', metadata, autoload_with=engine)
document_chunks = Table('document_chunks', metadata, autoload_with=engine)


# --- Data Cleaning Functions (Phase 1+3) ---

import re
from typing import Tuple, List, Dict, Any

def _is_code_block(text: str) -> bool:
    """
    判斷文字是否為程式碼區塊
    
    改進版：提高檢測門檻，避免誤判一般技術文章為程式碼
    """
    if not text or len(text) < 20:  # ✅ 提高最小長度要求
        return False
    
    lines = text.split('\n')
    if len(lines) < 3:  # ✅ 要求至少3行
        return False
    
    code_indicators = 0
    total_lines = len(lines)
    
    # 強烈的程式碼指標
    strong_patterns = [
        r'^\s*(def|class|import|from .+ import)\s',  # Python 關鍵字
        r'^\s*(function|const|let|var|if|for|while)\s',  # JavaScript
        r'^\s*(public|private|void|int|String)\s',  # Java/C#
        r'[{}\[\]();].*[{}\[\]();]',  # 多個程式碼符號在同一行
        r'^\s*//.*$|^\s*/\*.*\*/$',  # 註解
    ]
    
    # 弱指標（需要更多數量才算）
    weak_patterns = [
        r'[=<>!]=|[+\-*/]=',  # 運算符
        r'\{.*\}',  # 單個 {}
    ]
    
    for line in lines:
        if not line.strip():
            continue
        
        # 檢查強指標
        for pattern in strong_patterns:
            if re.search(pattern, line):
                code_indicators += 2  # 強指標權重更高
                break
        else:
            # 檢查弱指標
            for pattern in weak_patterns:
                if re.search(pattern, line):
                    code_indicators += 0.5  # 弱指標權重低
                    break
    
    # ✅ 提高門檻：需要超過40%的行符合程式碼模式
    code_ratio = code_indicators / total_lines
    return code_ratio > 0.4


def _clean_text(text: str) -> str:
    """
    清理文字（標準化格式，移除噪音）
    
    處理:
    - 頁碼：移除單獨的頁碼行（text_splitter 會統一添加 [Page N]）
    - 頁碼佔位符：移除 ‹#› 等符號
    - 教師資訊：移除（非教學內容）
    - 多餘的空白和換行：標準化
    """
    if not text:
        return ""
    
    # 移除單獨的頁碼行（1-3位數字）
    text = re.sub(r'^\d{1,3}$', '', text, flags=re.MULTILINE)
    
    # 移除 ‹#› 符號（可能是頁碼佔位符）
    text = re.sub(r'‹#›', '', text)
    
    # 移除教師資訊（特定格式）
    text = re.sub(r'資訊科學系.*?@mail\.ntue\.edu\.tw', '', text, flags=re.DOTALL)
    
    # 標準化換行（3個以上換行變成2個）
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    # 標準化空格（2個以上空格變成1個）
    text = re.sub(r' {2,}', ' ', text)
    
    return text.strip()


def _post_process_ocr(text: str) -> str:
    """
    OCR 後處理：移除噪音、修正常見錯誤
    
    策略：
    - 移除 OCR 噪音字元（來自圖標、線條等）
    - 修正數字間多餘空格
    - 過濾極短的片段
    - 移除純符號行
    """
    if not text:
        return ""
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        line = line.strip()
        
        # ✅ 跳過空行
        if not line:
            continue
        
        # ✅ 跳過極短的行（<2 字符，可能是噪音）
        if len(line) < 2:
            continue
        
        # ✅ 跳過純符號行（如 "===", "---", "|||"）
        if all(c in '=-_|/\\*+~`^<>[]{}()' for c in line.replace(' ', '')):
            continue
        
        # ✅ 跳過過多符號的行（>50% 是符號）
        symbol_count = sum(1 for c in line if not c.isalnum() and c not in ' \n\t')
        if len(line) > 0 and symbol_count / len(line) > 0.5:
            continue
        
        # ✅ 移除明顯的 OCR 噪音字元（保留中文、英文、數字、常見標點）
        line = re.sub(r'[^\w\s\u4e00-\u9fff.,!?;:()\\[\\]{}"\'+\\-=/*<>%$&@#]', '', line)
        
        # ✅ 修正數字間多餘空格（例如：「1 2 3」→「123」）
        line = re.sub(r'(\d)\s+(\d)', r'\1\2', line)
        
        # ✅ 移除多餘的空白
        line = ' '.join(line.split())
        
        if line:  # 最後檢查是否還有內容
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def _clean_and_prepare_multimodal_content(
    structured_elements: List[Dict],
    job_id: Optional[int] = None,
    parent_task_id: Optional[int] = None
) -> Tuple[str, Dict]:
    """
    清理內容並準備多模態 metadata
    
    策略:
    - 程式碼：保留但用 [Code] 標記（因為很多教材是程式碼教學）
    - 頁碼：保留為 [Page N] 格式（用於 source 參考）
    - 圖片：保留完整 base64 + 清理後的 OCR
    
    Args:
        structured_elements: List of {"type": "text"|"image", ...}
    
    Returns:
        (text_for_chunking, multimodal_metadata)
    """
    text_parts = []
    images = []
    current_pos = 0
    contains_code = False
    
    for elem in structured_elements:
        if elem.get("type") == "text":
            content = elem["content"]
            
            # 檢測程式碼（標記但不過濾）
            is_code = _is_code_block(content)
            if is_code:
                contains_code = True
            
            # 清理文字
            cleaned = _clean_text(content)
            if cleaned:
                # 如果是程式碼，用更乾淨的格式表達
                if is_code:
                    # 移除過多的空白，但保留程式碼結構
                    cleaned = re.sub(r' {4,}', '    ', cleaned)  # 統一縮排為4空格
                    cleaned = f"[Code]\n{cleaned}\n[/Code]"
                
                text_parts.append(cleaned)
                current_pos += len(cleaned) + 1  # +1 for space
        
        elif elem.get("type") == "image":
            # 保存完整圖片資訊
            vision_desc = elem.get("vision_description", "")
            vision_tokens = elem.get("vision_tokens", 0)
            vision_cost = elem.get("vision_cost", 0.0)
            cleaned_desc = _post_process_ocr(vision_desc)
            
            
            images.append({
                "position": current_pos,
                "base64": elem["base64"],
                "vision_description": cleaned_desc,
                "vision_tokens": vision_tokens,
                "vision_cost": vision_cost
            })
            
            # 在 text_for_chunking 中加入 Vision 描述
            if cleaned_desc:
                vision_marker = f"<圖片描述>\n{cleaned_desc}\n</圖片描述>"
                text_parts.append(vision_marker)
                current_pos += len(vision_marker) + 1
    
    text_for_chunking = " ".join(text_parts)
    
    multimodal_metadata = {
        "images": images,
        "contains_code": contains_code,
    }
    
    return text_for_chunking, multimodal_metadata

# --- Main Orchestrator Logic ---
def process_file(file_path: str, uploader_id: int, course_id: int, course_unit_id: int = None, force_reprocess: bool = False) -> tuple[int | None, bool]:
    """
    Processes a single file for ingestion, using the new db_logger for all logging.
    
    Returns:
        tuple[int | None, bool]: (unique_content_id, was_skipped)
            - unique_content_id: ID of the content, or None if failed
            - was_skipped: True if file already existed and was skipped, False otherwise
    """
    file_name = os.path.basename(file_path)
    
    job_id = db_logger.create_job(
        user_id=uploader_id,
        input_prompt=f"[INGEST] Uploaded file: {file_name}",
        workflow_type='ingestion'
    )
    if not job_id:
        print(f"ERROR: Failed to create an ingestion job for file '{file_name}'. Aborting.")
        return None

    try:
        with engine.connect() as conn:
            with conn.begin() as transaction:
                last_task_id = None # Initialize for sequential parent_task_id logging

                # --- Task 1: Hashing and Get-Or-Create Unique Content ---
                task_id_hash = db_logger.create_task(job_id, "hash_file", "Calculate file hash and check for existence.", task_input={"file_path": file_path}, parent_task_id=last_task_id)
                last_task_id = task_id_hash
                start_time = time.perf_counter()
                
                # ✅ 處理 URL 和本地文件的不同情況
                is_url = file_path.startswith('http://') or file_path.startswith('https://')
                
                if is_url:
                    # URL: 使用 URL 本身作為 hash 基礎
                    file_hash = hashlib.sha256(file_path.encode('utf-8')).hexdigest()
                    file_bytes = b''  # URL 沒有實際文件大小
                    file_size = 0
                else:
                    # 本地文件: 讀取並計算 hash
                    with open(file_path, "rb") as f:
                        file_bytes = f.read()
                        file_hash = hashlib.sha256(file_bytes).hexdigest()
                        file_size = len(file_bytes)
                
                existing_id = conn.execute(select(unique_contents.c.id).where(unique_contents.c.content_hash == file_hash)).scalar_one_or_none()
                
                unique_content_id = None
                if existing_id and not force_reprocess:
                    unique_content_id = existing_id
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    db_logger.update_task(task_id_hash, 'completed', f"Content already exists with ID {unique_content_id}.", duration_ms=duration_ms)
                else:
                    if existing_id: # force_reprocess is True
                        conn.execute(delete(unique_contents).where(unique_contents.c.id == existing_id))
                    
                    # ✅ 對於 URL，file_type 設為 'web'
                    if is_url:
                        file_type = 'web'
                    else:
                        file_type = file_name.split('.')[-1] if '.' in file_name else 'unknown'
                    
                    insert_stmt = insert(unique_contents).values(
                        content_hash=file_hash, 
                        file_size_bytes=file_size,
                        original_file_type=file_type,  # ✅ 使用 file_type 變數
                        processing_status='in_progress'
                    ).returning(unique_contents.c.id)
                    unique_content_id = conn.execute(insert_stmt).scalar_one()
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    db_logger.update_task(task_id_hash, 'completed', f"Created new unique_content with ID {unique_content_id}.", duration_ms=duration_ms)

                # --- Task 2: Link Material to Course ---
                task_id_link = db_logger.create_task(job_id, "link_material", "Link content to course.", task_input={"unique_content_id": unique_content_id, "course_id": course_id, "uploader_id": uploader_id}, parent_task_id=last_task_id)
                last_task_id = task_id_link
                start_time = time.perf_counter()
                
                if not conn.execute(select(uploaded_contents.c.id).where((uploaded_contents.c.unique_content_id == unique_content_id) & (uploaded_contents.c.course_id == course_id))).scalar_one_or_none():
                    conn.execute(insert(uploaded_contents).values(
                        unique_content_id=unique_content_id, course_id=course_id,
                        uploader_id=uploader_id, file_name=file_name
                    ))
                
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                db_logger.update_task(task_id_link, 'completed', f"Linked content {unique_content_id} to course {course_id}.", duration_ms=duration_ms)

                if existing_id and not force_reprocess:
                    db_logger.update_job_status(job_id, 'completed')
                    return unique_content_id, True  # ✅ 返回 tuple，標記為已跳過

                # --- Task 3: Document Loading & Parsing ---
                from backend.app.services.document_loader import get_loader
                task_id_load = db_logger.create_task(job_id, "document_loader", "Load and extract text from file.", task_input={"file_path": file_path}, parent_task_id=last_task_id)
                last_task_id = task_id_load
                start_time = time.perf_counter()
                document = get_loader(file_path).load(file_path)
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                db_logger.update_task(task_id_load, 'completed', f"Loaded {len(document.pages)} pages.", duration_ms=duration_ms)

                # --- Task 4: Save Document Content ---
                task_id_save_content = db_logger.create_task(job_id, "database_writer", "Save page-by-page content.", task_input={"unique_content_id": unique_content_id}, parent_task_id=last_task_id)
                last_task_id = task_id_save_content
                start_time = time.perf_counter()
                preview_data = []
                
                for page in document.pages:
                    structured_json = getattr(page, 'structured_elements', [])
                    
                    # ✅ 傳入 job_id 和 parent_task_id 用於 Vision LLM 任務記錄
                    text_for_chunking, mm_metadata = _clean_and_prepare_multimodal_content(
                        structured_json,
                        job_id=job_id,
                        parent_task_id=task_id_load
                    )
                    
                    # 暫存在 Page 物件（供 text_splitter 使用）
                    page.text_for_chunking = text_for_chunking
                    page.multimodal_metadata = mm_metadata
                    
                    if structured_json:
                        preview_data.append({
                            "unique_content_id": unique_content_id,
                            "page_number": page.page_number,
                            "structured_content": structured_json,  # ✅ 完整保留（含 base64）
                            "combined_human_text": text_for_chunking  # ✅ 純文字+OCR（不含 base64）
                        })
                
                if preview_data:
                    conn.execute(insert(document_content), preview_data)
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                db_logger.update_task(task_id_save_content, 'completed', f"Saved {len(preview_data)} pages of content.", duration_ms=duration_ms)

                # ✅ 聚合 Vision LLM 成本記錄
                total_vision_tokens = 0
                total_vision_cost = 0.0
                total_images = 0
                
                for page in document.pages:
                    mm_metadata = getattr(page, 'multimodal_metadata', {})
                    for img in mm_metadata.get('images', []):
                        total_vision_tokens += img.get('vision_tokens', 0)
                        total_vision_cost += img.get('vision_cost', 0.0)
                        total_images += 1
                
                # 如果有圖片處理，創建單一 vision_llm 任務記錄
                if total_images > 0:
                    vision_task_id = db_logger.create_task(
                        job_id=job_id,
                        agent_name="vision_llm",
                        task_description=f"Generate vision descriptions for {total_images} images",
                        task_input={"vision_model": os.getenv("VISION_MODEL", "gpt-4o-mini")},
                        parent_task_id=task_id_load
                    )
                    
                    if vision_task_id:
                        db_logger.update_task(
                            task_id=vision_task_id,
                            status='completed',
                            output={"total_images": total_images, "avg_cost_per_image": total_vision_cost / total_images if total_images > 0 else 0},
                            prompt_tokens=total_vision_tokens,
                            completion_tokens=0,
                            estimated_cost_usd=total_vision_cost,
                            model_name=os.getenv("VISION_MODEL", "gpt-4o-mini"),
                            duration_ms=1
                        )


                # --- Task 5: Document Chunking ---
                from backend.app.services.text_splitter import chunk_document
                chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
                chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "150"))
                task_id_chunk = db_logger.create_task(job_id, "text_splitter", "Split document into chunks.", task_input={"chunk_size": chunk_size, "chunk_overlap": chunk_overlap}, parent_task_id=last_task_id)
                last_task_id = task_id_chunk
                start_time = time.perf_counter()
                chunks_with_metadata = chunk_document(pages=document.pages, chunk_size=chunk_size, chunk_overlap=chunk_overlap, file_name=file_name, uploader_id=uploader_id)
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                db_logger.update_task(task_id_chunk, 'completed', f"Created {len(chunks_with_metadata)} chunks.", duration_ms=duration_ms)

                # --- Task 6: Generate Embeddings and Store Chunks ---
                task_id_embed = db_logger.create_task(job_id, "embedding_generator", "Generate embeddings and save chunks.", task_input={"num_chunks_to_embed": len(chunks_with_metadata) if chunks_with_metadata else 0}, parent_task_id=last_task_id)
                last_task_id = task_id_embed
                start_time = time.perf_counter()
                if chunks_with_metadata:
                    from backend.app.services.embedding_service import embedding_service
                    
                    # ✅ 處理三元組格式 (text, metadata, multimodal_metadata)
                    # 如果 text_splitter 尚未更新，則 chunks_with_metadata 可能是二元組
                    # 我們需要向後兼容
                    if chunks_with_metadata and len(chunks_with_metadata[0]) == 3:
                        # 三元組格式（已更新）
                        texts_to_embed = [text for text, meta, mm_meta in chunks_with_metadata]
                        
                        # ✅ 先生成 embeddings
                        embeddings, usage = embedding_service.create_embeddings(texts_to_embed)
                        
                        chunk_data = [
                            {
                                "unique_content_id": unique_content_id,
                                "chunk_text": text,
                                "chunk_order": i,
                                "metadata": meta,
                                "multimodal_metadata": mm_meta,  # ✅ 新增！
                                "embedding": embedding
                            }
                            for i, ((text, meta, mm_meta), embedding) in enumerate(zip(chunks_with_metadata, embeddings))
                        ]
                    else:
                        # 二元組格式（向後兼容）
                        texts_to_embed = [text for text, meta in chunks_with_metadata]
                        
                        # ✅ 先生成 embeddings
                        embeddings, usage = embedding_service.create_embeddings(texts_to_embed)
                        
                        chunk_data = [
                            {
                                "unique_content_id": unique_content_id,
                                "chunk_text": text,
                                "chunk_order": i,
                                "metadata": meta,
                                "multimodal_metadata": None,  # 舊格式沒有 multimodal_metadata
                                "embedding": embedding
                            }
                            for i, ((text, meta), embedding) in enumerate(zip(chunks_with_metadata, embeddings))
                        ]
                    
                    conn.execute(insert(document_chunks), chunk_data)
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    
                    # 計算 embedding 成本
                    # text-embedding-3-small: $0.00002 per 1K tokens
                    # text-embedding-3-large: $0.00013 per 1K tokens
                    total_tokens = usage.get("total_tokens", 0)
                    model = embedding_service._model_name
                    if "large" in model:
                        cost_per_1k = 0.00013
                    else:  # small or default
                        cost_per_1k = 0.00002
                    estimated_cost = (total_tokens / 1000.0) * cost_per_1k
                    
                    # Embedding API 只返回 total_tokens 和 prompt_tokens（相同值）
                    # db_logger 使用 prompt_tokens 來計算成本
                    db_logger.update_task(
                        task_id_embed, 
                        'completed', 
                        f"Saved {len(chunk_data)} chunks.", 
                        duration_ms=duration_ms, 
                        prompt_tokens=total_tokens,  # ✅ 使用 total_tokens
                        model_name=model,  # ✅ 模型名稱
                        estimated_cost_usd=estimated_cost  # ✅ 計算成本
                    )
                else:
                    duration_ms = int((time.perf_counter() - start_time) * 1000)
                    db_logger.update_task(task_id_embed, 'completed', "No chunks to embed.", duration_ms=duration_ms)

                # --- Task 7: Finalize Status ---
                task_id_finalize = db_logger.create_task(job_id, "finalize_status", "Update unique_content status to completed.", task_input={"unique_content_id": unique_content_id}, parent_task_id=last_task_id)
                last_task_id = task_id_finalize
                start_time = time.perf_counter()
                conn.execute(update(unique_contents).where(unique_contents.c.id == unique_content_id).values(processing_status='completed'))
                duration_ms = int((time.perf_counter() - start_time) * 1000)
                db_logger.update_task(task_id_finalize, 'completed', duration_ms=duration_ms)

        db_logger.update_job_status(job_id, 'completed')
        print(f"\nSuccessfully processed and INGESTED file '{file_name}'.")
        return unique_content_id, False  # ✅ 返回 tuple，標記為新 ingest

    except Exception as e:
        print(f"ERROR: An error occurred during file ingestion for job {job_id}. Error: {e}")
        db_logger.update_job_status(job_id, 'failed', error_message=str(e))
        # The transaction will be rolled back automatically by the 'with' statement context manager
        return None, False  # ✅ 返回 tuple

if __name__ == '__main__':
    # This block remains for direct testing of the ingestion process
    FORCE_REPROCESS = False
    print(f"--- Starting Multimodal Document Ingestion Test (Force Reprocess: {FORCE_REPROCESS}) ---")
    TEST_FILES_DIR = "test_files"
    if not os.path.isdir(TEST_FILES_DIR):
        print(f"Error: Test files directory not found at '{TEST_FILES_DIR}'.")
        exit()
    
    test_files = ["sample.pptx"] 
    
    for test_file in test_files:
        test_file_path = os.path.join(TEST_FILES_DIR, test_file)
        print("\n" + "="*50 + f"\nProcessing file: {test_file_path}\n" + "="*50)
        try:
            content_id, was_skipped = process_file(file_path=test_file_path, uploader_id=1, course_id=1, force_reprocess=FORCE_REPROCESS)
            if content_id:
                status = "skipped (already exists)" if was_skipped else "successfully ingested"
                print(f"\n--- File {status}. Unique Content ID: {content_id} ---")
            else:
                print(f"\n--- Failed to process file: {test_file_path} ---")
        except Exception as e:
            print(f"!!! FAILED to process {test_file_path}: {e} !!!")
    print("\n--- All Document Ingestion Tests Finished ---")