from typing import List, Tuple, Dict, Any
from backend.app.services.document_loader import Page

def chunk_document(
    pages: List[Page],
    chunk_size: int,
    chunk_overlap: int,
    file_name: str,
    uploader_id: int
) -> List[Tuple[str, Dict[str, Any], Dict[str, Any]]]:
    """
    使用滑動視窗策略將文檔切分成 chunks
    
    策略：
    1. 建立完整文字（每頁前加 [Page N] 標記）
    2. 使用滑動視窗，每次前進 (chunk_size - chunk_overlap)
    3. 在視窗邊界尋找分隔符，避免句子中間切斷
    
    Returns:
        List of (chunk_text, page_metadata, multimodal_metadata)
    """
    
    # 分隔符優先級
    SEPARATORS = ["\n\n", "\n", "。", "！", "？", ". ", " "]
    
    # 1. 建立完整文字和映射
    full_text = ""
    char_to_page_map = []
    char_to_image_map = []
    page_code_flags = {}
    
    for page in pages:
        page_text = page.text_for_chunking
        if not page_text:
            continue
        
        start_index = len(full_text)
        
        # 在每個頁面文字前插入 [Page N] 標記
        page_marker = f"[Page {page.page_number}] "
        full_text += page_marker + page_text + "\n\n"
        end_index = len(full_text)
        
        # 映射字元到頁碼
        for i in range(start_index, end_index):
            char_to_page_map.append(page.page_number)
        
        # 記錄頁面程式碼標記
        mm_meta = getattr(page, 'multimodal_metadata', None)
        if mm_meta:
            page_code_flags[page.page_number] = mm_meta.get('contains_code', False)
        
        # 映射圖片位置
        if mm_meta and mm_meta.get('images'):
            for img in mm_meta['images']:
                absolute_pos = start_index + len(page_marker) + img['position']
                char_to_image_map.append((absolute_pos, img, page.page_number))
    
    if not full_text:
        return []
    
    # 2. 簡化的滑動視窗切分
    chunks_with_metadata = []
    start_idx = 0
    
    while start_idx < len(full_text):
        # 計算結束位置
        end_idx = min(start_idx + chunk_size, len(full_text))
        
        # 如果不是最後一個 chunk，嘗試在分隔符處切分
        if end_idx < len(full_text):
            # 在結束位置附近尋找分隔符（向前看最多 200 字符）
            search_from = max(start_idx, end_idx - 200)
            search_region = full_text[search_from:end_idx]
            
            # 嘗試每個分隔符
            best_split = None
            for sep in SEPARATORS:
                if sep in search_region:
                    # 找最後一個分隔符
                    pos = search_region.rfind(sep)
                    if pos != -1:
                        best_split = search_from + pos + len(sep)
                        break
            
            # 如果找到好的切分點，使用它
            if best_split and best_split > start_idx:
                end_idx = best_split
        
        # 提取 chunk 文字
        chunk_text = full_text[start_idx:end_idx].strip()
        
        if chunk_text:
            # 確定頁碼範圍
            page_numbers = []
            if start_idx < len(char_to_page_map) and end_idx <= len(char_to_page_map):
                start_page = char_to_page_map[start_idx]
                end_page = char_to_page_map[min(end_idx - 1, len(char_to_page_map) - 1)]
                page_numbers = sorted(list(set(range(start_page, end_page + 1))))
            
            # 確定包含的圖片
            chunk_images = []
            for img_pos, img_data, img_page in char_to_image_map:
                if start_idx <= img_pos < end_idx:
                    relative_pos = img_pos - start_idx
                    chunk_images.append({
                        "position": relative_pos,
                        "base64": img_data["base64"],
                        "vision_description": img_data.get("vision_description", ""),
                        "vision_tokens": img_data.get("vision_tokens", 0),
                        "vision_cost": img_data.get("vision_cost", 0.0)
                    })
            
            # 確定是否包含程式碼
            chunk_contains_code = any(
                page_code_flags.get(page_num, False)
                for page_num in page_numbers
            )
            
            # 構建 metadata
            page_meta = {"page_numbers": page_numbers}
            mm_meta = {
                "images": chunk_images,
                "contains_code": chunk_contains_code
            }
            
            chunks_with_metadata.append((chunk_text, page_meta, mm_meta))
        
        # 移動到下一個位置（滑動視窗）
        # 計算最小前進距離（避免產生太多重疊的小 chunks）
        min_advance = max(chunk_size - chunk_overlap, 100)  # 至少前進 100 字符或 (size - overlap)
        
        # 理論下一個起點
        theoretical_next = start_idx + min_advance
        
        # 如果理論起點在文字範圍內，嘗試找到一個乾淨的起始位置
        if theoretical_next < len(full_text):
            # 在 theoretical_next 附近向後尋找分隔符（最多向後看 100 字符）
            search_start = max(0, theoretical_next - 100)
            search_region = full_text[search_start:theoretical_next + 50]
            
            # 嘗試找到最接近 theoretical_next 的分隔符
            best_start = None
            for sep in SEPARATORS:
                # 找這個分隔符在搜索區域中的所有位置
                pos = theoretical_next - search_start  # 相對於 search_region 的目標位置
                
                # 向前找最近的分隔符結束位置
                last_sep_pos = search_region.rfind(sep, 0, pos + 50)
                if last_sep_pos != -1:
                    absolute_pos = search_start + last_sep_pos + len(sep)
                    # 確保這個位置比 start_idx 大
                    if absolute_pos > start_idx + 50:  # 至少前進 50 字符
                        best_start = absolute_pos
                        break
            
            if best_start:
                start_idx = best_start
            else:
                start_idx = theoretical_next
        else:
            start_idx = theoretical_next
        
        # 防止無限循環
        if start_idx >= len(full_text) - 1:
            break
    
    return chunks_with_metadata
