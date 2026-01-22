from __future__ import print_function

import os.path
import io
import re

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from . import Document, DocumentLoader, get_loader

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

class GoogleDriveLoader(DocumentLoader):
    """A loader for Google Drive files that downloads content and passes it to appropriate loaders."""

    def __init__(self):
        self.creds = self._authenticate()
        self.service = build('drive', 'v3', credentials=self.creds)

    def _authenticate(self):
        creds = None
        # The file token.json stores the user's access and refresh tokens, and is
        # created automatically when the authorization flow completes for the first
        # time.
        if os.path.exists('token.json'):
            creds = Credentials.from_authorized_user_file('token.json', SCOPES)
        # If there are no (valid) credentials available, let the user log in.
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                # Ensure credentials.json is in the backend directory
                if not os.path.exists('credentials.json'):
                    raise FileNotFoundError(
                        "credentials.json not found. Please download it from Google Cloud Console "
                        "(API & Services -> Credentials -> OAuth 2.0 Client IDs -> Download JSON) "
                        "and place it in the backend directory."
                    )
                flow = InstalledAppFlow.from_client_secrets_file(
                    'credentials.json', SCOPES)
                creds = flow.run_local_server(port=0)
            # Save the credentials for the next run
            with open('token.json', 'w') as token: # Changed to 'w' to overwrite if needed
                token.write(creds.to_json())
        return creds

    def _get_file_id_from_source(self, source: str) -> str:
        # Check if it's a direct file ID
        if re.match(r"^[a-zA-Z0-9_-]{28,33}$", source):
            return source
        
        # Check if it's a shareable link
        match = re.search(r"id=([a-zA-Z0-9_-]+)", source)
        if match:
            return match.group(1)
        match = re.search(r"/d/([a-zA-Z0-9_-]+)", source)
        if match:
            return match.group(1)
        
        raise ValueError(f"Invalid Google Drive source: {source}. Must be a file ID or a shareable link.")

    def load(self, source: str) -> Document:
        """Downloads a Google Drive file and processes it using the appropriate loader."""
        file_id = self._get_file_id_from_source(source)
        
        try:
            # Get file metadata to determine its name and MIME type
            file_metadata = self.service.files().get(fileId=file_id, fields="name,mimeType").execute()
            file_name = file_metadata.get('name', 'downloaded_file')
            mime_type = file_metadata.get('mimeType', 'application/octet-stream')

            print(f"Downloading file '{file_name}' (MIME type: {mime_type}) from Google Drive...")

            # Download the file content
            request = self.service.files().get_media(fileId=file_id)
            file_content_io = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content_io, request)
            done = False
            while done is False:
                status, done = downloader.next_chunk()
                print(f"Download {int(status.progress() * 100)}%.")
            file_content_io.seek(0)

            # Determine file extension from name or MIME type
            _, ext = os.path.splitext(file_name)
            if not ext:
                # Try to infer extension from MIME type if not in name
                if 'pdf' in mime_type: ext = '.pdf'
                elif 'document' in mime_type or 'word' in mime_type: ext = '.docx'
                elif 'presentation' in mime_type: ext = '.pptx'
                elif 'text' in mime_type: ext = '.txt'
                elif 'image' in mime_type: ext = '.png' # Default image type
            
            # Create a temporary file to pass to get_loader
            # This is a workaround as get_loader expects a file path
            # A more robust solution would be to modify get_loader to accept BytesIO
            temp_file_path = f"/tmp/{file_id}{ext}"
            with open(temp_file_path, 'wb') as temp_file:
                temp_file.write(file_content_io.read())
            
            # Use the main get_loader to process the downloaded file
            # This will use our existing loaders (PdfLoader, DocxLoader, etc.)
            loader = get_loader(temp_file_path)
            document = loader.load(temp_file_path)

            # Clean up temporary file
            os.remove(temp_file_path)

            document.source = source # Override source to be the original Drive ID/URL
            print(f"Successfully processed Google Drive file: {source}")
            return document

        except HttpError as error:
            print(f"An HTTP error occurred: {error}")
            raise error
        except Exception as e:
            print(f"Error processing Google Drive file {source}: {str(e)}")
            raise e
