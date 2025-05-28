# gmail/gmail_service.py
import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from Vendor_email_logger_agent.config import settings

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
CREDENTIALS_PATH = os.path.join(BASE_DIR, 'credentials.json')

def get_gmail_service():
    creds = None
    flow = InstalledAppFlow.from_client_secrets_file(
        CREDENTIALS_PATH, SCOPES)
    creds = flow.run_local_server(port=8000)
    service = build('gmail', 'v1', credentials=creds)
    return service
