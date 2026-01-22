from . import Document, Page, DocumentLoader
from .vision_utils import process_image_with_vision
import base64
from PIL import Image
import io

class ImageLoader(DocumentLoader):
    """A loader for image files (.png, .jpg, .jpeg)."""

    def load(self, source: str) -> Document:
        """Loads an image, uses Vision LLM for description, and returns structured_elements format."""
        try:
            # Open and encode image
            with open(source, "rb") as img_file:
                img_bytes = img_file.read()
            
            # Convert to base64 data URI
            img = Image.open(io.BytesIO(img_bytes))
            img_format = img.format.lower() if img.format else 'png'
            base64_str = base64.b64encode(img_bytes).decode('utf-8')
            base64_uri = f"data:image/{img_format};base64,{base64_str}"
            
            # ✅ Use Vision LLM (mandatory)
            vision_result = process_image_with_vision(img_bytes)
            
            # Convert to structured_elements format
            structured_elements = [
                {
                    "type": "image",
                    "base64": base64_uri,
                    "vision_description": vision_result["description"],
                    "vision_tokens": vision_result["total_tokens"],
                    "vision_cost": vision_result["cost"]
                }
            ]
            
            single_page = Page(page_number=1, structured_elements=structured_elements)
            
            print(f"✅ Successfully loaded image file (Vision LLM: {vision_result['total_tokens']} tokens)")
            return Document(source=source, pages=[single_page])
        except Exception as e:
            print(f"Error reading image file: {str(e)}")
            raise e
