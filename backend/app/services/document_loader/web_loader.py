from . import Document, Page, DocumentLoader
from langchain_community.document_loaders import WebBaseLoader
from bs4 import BeautifulSoup
import requests
from urllib.parse import urljoin
from .image_utils import image_to_base64_uri
from .vision_utils import process_image_with_vision

class WebLoader(DocumentLoader):
    """A loader for web pages using LangChain's WebBaseLoader and BeautifulSoup for images."""

    def load(self, source: str) -> Document:
        """Loads a web page, uses Vision LLM on images, and returns structured_elements format."""
        try:
            # Fetch the web page
            response = requests.get(source, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # ✅ 優先保留主要內容
            main_content = None
            for selector in ['article', 'main', '[role="main"]', '.post-content', '.entry-content', '.article-content']:
                main_content = soup.select_one(selector)
                if main_content:
                    soup = BeautifulSoup(str(main_content), 'html.parser')
                    break
            
            # 移除腳本和樣式
            if main_content:
                for tag in soup.find_all(['script', 'style', 'noscript', 'iframe']):
                    tag.decompose()
            else:
                tags_to_remove = ['script', 'style', 'noscript', 'iframe', 'nav', 'footer']
                for tag_name in tags_to_remove:
                    for tag in soup.find_all(tag_name):
                        tag.decompose()
            
            # Extract text
            text_content = soup.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in text_content.split('\n') if line.strip()]
            
            # 合併連續重複短行
            filtered_lines = []
            prev_line = None
            for line in lines:
                if len(line) < 30 and line == prev_line:
                    continue
                filtered_lines.append(line)
                prev_line = line
            
            text_content = '\n'.join(filtered_lines)
            
            # Process images
            images = []
            for idx, img_tag in enumerate(soup.find_all('img')):
                img_src = img_tag.get('src') or img_tag.get('data-src')
                if not img_src:
                    continue
                
                # Handle relative URLs
                if img_src.startswith('//'):
                    img_src = 'https:' + img_src
                elif img_src.startswith('/'):
                    from urllib.parse import urlparse
                    base_url = f"{urlparse(source).scheme}://{urlparse(source).netloc}"
                    img_src = urljoin(base_url, img_src)
                elif not img_src.startswith('http'):
                    img_src = urljoin(source, img_src)
                
                try:
                    # Download and process image
                    img_response = requests.get(img_src, timeout=10)
                    img_response.raise_for_status()
                    img_bytes = img_response.content
                    
                    # Convert to base64 URI
                    base64_uri = image_to_base64_uri(img_bytes)
                    
                    # Use Vision LLM
                    vision_result = process_image_with_vision(img_bytes)
                    
                    images.append({
                        "type": "image",
                        "base64": base64_uri,
                        "vision_description": vision_result["description"],
                        "vision_tokens": vision_result["total_tokens"],
                        "vision_cost": vision_result["cost"],
                        "position": len(text_content) + idx * 100
                    })
                except Exception as img_error:
                    print(f"Warning: Failed to process image {img_src}: {str(img_error)}")
                    continue
            
            # Build structured_elements
            structured_elements = []
            
            # Add text
            if text_content:
                structured_elements.append({
                    "type": "text",
                    "content": text_content
                })
            
            # Add images
            structured_elements.extend(images)
            
            single_page = Page(page_number=1, structured_elements=structured_elements)
            
            print(f"✅ Successfully read from URL: {source}")
            return Document(source=source, pages=[single_page])
            
        except Exception as e:
            print(f"Error reading URL {source}: {str(e)}")
            raise e
