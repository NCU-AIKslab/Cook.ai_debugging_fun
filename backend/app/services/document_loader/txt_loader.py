from . import Document, Page, DocumentLoader

class TxtLoader(DocumentLoader):
    """A loader for plain text (.txt) files."""

    def load(self, source: str) -> Document:
        """Reads text from a .txt file using structured_elements format."""
        try:
            with open(source, "r", encoding="utf-8") as f:
                content = f.read()
            
            # Convert to structured_elements format
            structured_elements = []
            if content.strip():
                structured_elements.append({
                    "type": "text",
                    "content": content
                })
            
            single_page = Page(page_number=1, structured_elements=structured_elements)
            
            print(f"✅ Successfully loaded TXT file")
            return Document(source=source, pages=[single_page])
        except Exception as e:
            print(f"Error reading TXT file: {str(e)}")
            raise e
