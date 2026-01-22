import base64
import io
from PIL import Image

def image_to_base64_uri(image_bytes: bytes) -> str:
    """Converts raw image bytes to a base64 encoded PNG data URI."""
    try:
        # Open the raw image data with Pillow
        raw_image = io.BytesIO(image_bytes)
        pil_image = Image.open(raw_image)

        # Convert to PNG and write to an in-memory buffer
        with io.BytesIO() as buffer:
            pil_image.save(buffer, format="PNG")
            png_image_bytes = buffer.getvalue()

        # Encode the PNG bytes in base64
        base64_image = base64.b64encode(png_image_bytes).decode('utf-8')
        image_uri = f"data:image/png;base64,{base64_image}"
        return image_uri
    except Exception as e:
        print(f"Warning: Could not convert image to base64 URI: {e}")
        return ""
