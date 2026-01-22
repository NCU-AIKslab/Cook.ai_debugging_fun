"""
Document Loader Package

Provides loaders for various document formats:
- PDF
- PPTX
- DOCX
- TXT
- Images (PNG, JPG, JPEG)
- Web pages (HTML URLs)
- Google Drive
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Dict, Any

# Base classes
@dataclass
class Page:
    page_number: int
    structured_elements: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class Document:
    source: str
    pages: List[Page]

class DocumentLoader:
    def load(self, source: str) -> Document:
        raise NotImplementedError("Subclasses must implement the load method")

def get_loader(source: str) -> DocumentLoader:
    """
    Returns the appropriate loader based on file extension or URL.
    
    Args:
        source: File path or URL
    
    Returns:
        Appropriate DocumentLoader instance
    """
    # Check for Google Drive ID or URL first
    if re.match(r"^[a-zA-Z0-9_-]{28,33}$", source) or \
       re.search(r"id=([a-zA-Z0-9_-]+)", source) or \
       re.search(r"/d/([a-zA-Z0-9_-]+)", source):
        from .google_drive_loader import GoogleDriveLoader
        return GoogleDriveLoader()

    # Check for web URLs
    if source.startswith('http://') or source.startswith('https://'):
        from .web_loader import WebLoader
        return WebLoader()

    # Otherwise check file extension
    _, extension = os.path.splitext(source)
    extension = extension.lower()

    if extension == '.pdf':
        from .pdf_loader import PdfLoader
        return PdfLoader()
    elif extension == '.txt':
        from .txt_loader import TxtLoader
        return TxtLoader()
    elif extension == '.docx':
        from .docx_loader import DocxLoader
        return DocxLoader()
    elif extension == '.pptx':
        from .pptx_loader import PptxLoader
        return PptxLoader()
    elif extension in ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.webp']:
        from .image_loader import ImageLoader
        return ImageLoader()
    else:
        raise ValueError(f"Unsupported source type: {source}")
