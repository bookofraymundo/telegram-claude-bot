"""
One-time script to authorize Google Drive access and get a refresh token.
Saves auth URL to Desktop — open in personal Gmail browser.
"""
import webbrowser
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    'https://www.googleapis.com/auth/drive.file',
    'https://www.googleapis.com/auth/drive.readonly',
]
CREDS_FILE = '/Users/raymundosantacruz/Downloads/client_secret_867634606413-tqj8mds588aknp4c7vdknp4ml946ksae.apps.googleusercontent.com.json'

flow = InstalledAppFlow.from_client_secrets_file(CREDS_FILE, SCOPES)

# Generate auth URL
auth_url, _ = flow.authorization_url(access_type='offline', prompt='consent')

# Save URL to a file on Desktop
url_file = '/Users/raymundosantacruz/Desktop/OPEN_IN_PERSONAL_GMAIL.html'
with open(url_file, 'w') as f:
    f.write(f"""<!DOCTYPE html>
<html>
<body style="font-family:sans-serif;padding:40px">
<h2>Step 1: Open this page in the browser where your personal Gmail is signed in</h2>
<p>Then click the button below:</p>
<a href="{auth_url}" style="background:#E8651A;color:white;padding:14px 28px;text-decoration:none;border-radius:6px;font-size:16px">
  Authorize Google Drive Access
</a>
</body>
</html>""")

print(f"\n✅ File saved to your Desktop: OPEN_IN_PERSONAL_GMAIL.html")
print("Open that file in the browser with your personal Gmail (raymundosantacruz@gmail.com)")
print("\nWaiting for authorization (listening on http://localhost:8765)...\n")

# Start local server on fixed port to catch the callback
creds = flow.run_local_server(port=8765, open_browser=False)

print("\n✅ Authorization successful!\n")
print("Update GOOGLE_REFRESH_TOKEN in Railway to:\n")
print(creds.refresh_token)
