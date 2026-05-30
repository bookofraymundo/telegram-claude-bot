"""
Google Drive uploader for Santacruz Brothers LLC bot.
Uploads PDFs to SCBLLC/Estimates or SCBLLC/Invoices in Google Drive.
"""
import io
import os
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.readonly',
]
ROOT_FOLDER = 'SCBLLC'


def _get_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ['GOOGLE_REFRESH_TOKEN'],
        client_id=os.environ['GOOGLE_CLIENT_ID'],
        client_secret=os.environ['GOOGLE_CLIENT_SECRET'],
        token_uri='https://oauth2.googleapis.com/token',
        scopes=SCOPES,
    )
    return build('drive', 'v3', credentials=creds)


def _find_or_create_folder(service, name: str, parent_id: str = None) -> str:
    """Find a folder by name (under parent_id if given), or create it."""
    q = f"name='{name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    if parent_id:
        q += f" and '{parent_id}' in parents"
    results = service.files().list(q=q, fields='files(id, name)').execute()
    files = results.get('files', [])
    if files:
        return files[0]['id']
    # Create it
    meta = {'name': name, 'mimeType': 'application/vnd.google-apps.folder'}
    if parent_id:
        meta['parents'] = [parent_id]
    folder = service.files().create(body=meta, fields='id').execute()
    return folder['id']


def search_files(query: str, max_results: int = 5) -> list[dict]:
    """
    Search for files in SCBLLC folder matching the query.
    Returns list of {name, id, webViewLink, downloadUrl}
    """
    service = _get_service()
    root_id = _find_or_create_folder(service, ROOT_FOLDER)

    # Search by name containing query terms across all subfolders
    terms = query.strip().split()
    name_filters = ' and '.join(f"name contains '{t}'" for t in terms[:3])
    q = f"({name_filters}) and '{root_id}' in parents and trashed=false"
    # Also search subfolders
    results = service.files().list(
        q=f"fullText contains '{query}' and trashed=false",
        fields='files(id, name, webViewLink, mimeType, parents)',
        pageSize=20
    ).execute()
    files = results.get('files', [])
    # Filter to PDFs only
    pdfs = [f for f in files if 'pdf' in f.get('mimeType', '').lower() or f['name'].endswith('.pdf')]
    return pdfs[:max_results]


def download_file(file_id: str) -> bytes:
    """Download a file from Drive by ID and return bytes."""
    service = _get_service()
    request = service.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    from googleapiclient.http import MediaIoBaseDownload
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def upload_pdf(pdf_bytes: bytes, filename: str, subfolder: str) -> str:
    """
    Upload a PDF to SCBLLC/<subfolder>/ in Google Drive.
    subfolder: 'Estimates' or 'Invoices'
    Returns the shareable file URL.
    """
    service = _get_service()
    root_id = _find_or_create_folder(service, ROOT_FOLDER)
    sub_id  = _find_or_create_folder(service, subfolder, parent_id=root_id)

    file_meta = {'name': filename, 'parents': [sub_id]}
    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype='application/pdf')
    uploaded = service.files().create(
        body=file_meta,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    return uploaded.get('webViewLink', '')
