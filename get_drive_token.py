"""
One-time script to authorize Google Drive + Calendar access and get a refresh token.
Auto-opens browser for sign-in.
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/calendar.events',
]
CREDS_FILE = '/Users/raymundosantacruz/Downloads/client_secret_867634606413-tqj8mds588aknp4c7vdknp4ml946ksae.apps.googleusercontent.com.json'

flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)
creds = flow.run_local_server(port=0)

print("\n✅ Authorization successful!\n")
print("Update GOOGLE_REFRESH_TOKEN in Railway to:\n")
print(creds.refresh_token)
print(f"\nClient ID and Secret stay the same.")
