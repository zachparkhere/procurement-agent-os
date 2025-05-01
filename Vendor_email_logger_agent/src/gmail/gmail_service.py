# gmail/gmail_service.py
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

def get_gmail_service():
    creds = None
    flow = InstalledAppFlow.from_client_secrets_file(
        'credentials.json', SCOPES)
    creds = flow.run_local_server(port=8000)
    service = build('gmail', 'v1', credentials=creds)
    return service
