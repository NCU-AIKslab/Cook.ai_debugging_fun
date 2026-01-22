
import pdfplumber
import base64
import io
from PIL import Image
from . import Document, Page, DocumentLoader
from .vision_utils import process_image_with_vision
from .image_utils import image_to_base64_uri

class PdfLoader(DocumentLoader):
    """A loader for PDF files that extracts text and converts images to a web-safe format."""

    def load(self, source: str) -> Document:
        """Reads text and extracts/converts images from a PDF on a page-by-page basis."""

        doc_pages = []

        try:
            with pdfplumber.open(source) as pdf:
                for page_num, page in enumerate(pdf.pages):

                    # 處理文字
                    text_elements = []                    
                    for block in page.extract_text_lines(keep_blank_chars=True):
                        text_elements.append({
                            "type": "text",
                            "content": block["text"],
                            "top": block["top"]
                        })
                    
                    # 處理圖片
                    image_elements = []
                    for img in page.images:
                        image_data = img.get("stream").get_data() 
                        
                        if not image_data:
                            continue

                        base64_string = image_to_base64_uri(image_data)
                        vision_result = process_image_with_vision(image_data)

                        image_elements.append({
                            "type": "image",
                            "base64": base64_string,
                            "vision_description": vision_result["description"],
                            "vision_tokens": vision_result["total_tokens"],
                            "vision_cost": vision_result["cost"],
                            "top": img["top"]
                        })

                    # 依垂直位置排序並移除 top 欄位（一步完成）
                    structured_elements_for_this_page = [
                        {k: v for k, v in el.items() if k != "top"}
                        for el in sorted(text_elements + image_elements, key=lambda x: x["top"])
                    ]

                    # 建立新的 Page 物件
                    new_page_object = Page(
                        page_number=page_num + 1,
                        structured_elements=structured_elements_for_this_page
                    )
                    doc_pages.append(new_page_object)
                    
                print(f"Successfully read {len(doc_pages)} pages from {source}")
                return Document(source=source, pages=doc_pages)

        except Exception as e:
            print(f"Error reading PDF with pdfplumber: {str(e)}")
            raise e
