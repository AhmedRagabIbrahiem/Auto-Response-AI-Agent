from mcp.server.fastmcp import FastMCP
import mcp
import os
import pickle
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from pathlib import Path
from pypdf import PdfReader
import mcp.types as types
from typing import List, Optional, Union
import json


class AutoReplayServer:
    """The Server class for the autoreplay utilities"""
    def __init__(self, name: str):
        self.name = name
        self.Server = FastMCP(name)
        self.SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 
                       'https://www.googleapis.com/auth/gmail.send']
        
        # Register all tools
        self._register_tools()

    def get_mcp_server(self):
        return self.Server

    def get_gmail_service(self):
        """Authenticate and return Gmail API service"""
        creds = None
        
        # Load existing token if available
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If no valid credentials, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', self.SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save credentials for next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        return build('gmail', 'v1', credentials=creds)

    def _register_tools(self):
        """Register all MCP tools"""
        
        @self.Server.tool()
        async def get_latest_email() -> dict:
            """Fetch the most recent email from Gmail
            
                Args:[]"""
            try:
                service = self.get_gmail_service()
                
                # Get list of messages (maxResults=1 for the most recent)
                results = service.users().messages().list(
                    userId='me', 
                    maxResults=1
                ).execute()
                
                if 'messages' not in results:
                    return {"error": "No messages found", "success": False}
                
                # Get the most recent message
                message_id = results['messages'][0]['id']
                message = service.users().messages().get(
                    userId='me', 
                    id=message_id,
                    format='full'
                ).execute()
                
                # Extract headers
                headers = message['payload']['headers']
                email_data = {
                    "success": True,
                    "message_id": message_id
                }
                
                for header in headers:
                    if header['name'] in ['Subject', 'From', 'Date']:
                        email_data[header['name']] = header['value']
                
                # Get snippet (preview text)
                email_data['Snippet'] = message.get('snippet', '')
                
                return email_data
            except Exception as e:
                return {"error": str(e), "success": False}
        
        @self.Server.tool()
        async def send_email(
            to: Union[str, List[str]], 
            subject: str, 
            body: str, 
            cc: Optional[Union[str, List[str]]] = None, 
            bcc: Optional[Union[str, List[str]]] = None, 
            attachments: Optional[List[str]] = None
        ) -> dict:
            """
            Send an email using Gmail API
            
            Args:
                to: Recipient email address(es)
                subject: Email subject
                body: Email body text
                cc: CC recipient(s) (optional)
                bcc: BCC recipient(s) (optional)
                attachments: List of file paths to attach (optional)
            """
            try:
                service = self.get_gmail_service()
                
                # Create email message
                message = MIMEMultipart('alternative')
                
                # Handle recipients
                to_list = to if isinstance(to, list) else [to]
                message['to'] = ', '.join(to_list)
                
                if cc:
                    cc_list = cc if isinstance(cc, list) else [cc]
                    message['cc'] = ', '.join(cc_list)
                
                if bcc:
                    bcc_list = bcc if isinstance(bcc, list) else [bcc]
                    message['bcc'] = ', '.join(bcc_list)
                
                message['subject'] = subject
                
                # Add body as plain text
                text_part = MIMEText(body, 'plain')
                message.attach(text_part)
                
                # Add attachments if any
                if attachments:
                    for file_path in attachments:
                        try:
                            with open(file_path, 'rb') as attachment:
                                part = MIMEBase('application', 'octet-stream')
                                part.set_payload(attachment.read())
                                encoders.encode_base64(part)
                                part.add_header(
                                    'Content-Disposition',
                                    f'attachment; filename={os.path.basename(file_path)}'
                                )
                                message.attach(part)
                        except Exception as e:
                            return {"success": False, "error": f"Error attaching file {file_path}: {str(e)}"}
                
                # Encode the message
                encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
                
                # Create the message body
                create_message = {'raw': encoded_message}
                
                # Send the email
                sent_message = service.users().messages().send(
                    userId='me', 
                    body=create_message
                ).execute()
                
                return {"success": True, "message_id": sent_message['id']}
                
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.Server.tool()
        async def send_html_email(
            to: Union[str, List[str]], 
            subject: str, 
            html_body: str, 
            text_body: Optional[str] = None, 
            cc: Optional[Union[str, List[str]]] = None, 
            bcc: Optional[Union[str, List[str]]] = None, 
            attachments: Optional[List[str]] = None
        ) -> dict:
            """
            Send an HTML email using Gmail API
            
            Args:
                to: Recipient email address(es)
                subject: Email subject
                html_body: HTML email body
                text_body: Plain text fallback (optional)
                cc: CC recipient(s) (optional)
                bcc: BCC recipient(s) (optional)
                attachments: List of file paths to attach (optional)
            """
            try:
                service = self.get_gmail_service()
                
                # Create email message
                message = MIMEMultipart('alternative')
                
                # Handle recipients
                to_list = to if isinstance(to, list) else [to]
                message['to'] = ', '.join(to_list)
                
                if cc:
                    cc_list = cc if isinstance(cc, list) else [cc]
                    message['cc'] = ', '.join(cc_list)
                
                if bcc:
                    bcc_list = bcc if isinstance(bcc, list) else [bcc]
                    message['bcc'] = ', '.join(bcc_list)
                
                message['subject'] = subject
                
                # Add plain text version if provided, otherwise use stripped HTML
                if text_body:
                    text_part = MIMEText(text_body, 'plain')
                else:
                    # Simple HTML to text conversion
                    import re
                    text_body = re.sub(r'<[^>]+>', '', html_body)
                    text_part = MIMEText(text_body, 'plain')
                
                # Add HTML version
                html_part = MIMEText(html_body, 'html')
                
                message.attach(text_part)
                message.attach(html_part)
                
                # Add attachments if any
                if attachments:
                    for file_path in attachments:
                        try:
                            with open(file_path, 'rb') as attachment:
                                part = MIMEBase('application', 'octet-stream')
                                part.set_payload(attachment.read())
                                encoders.encode_base64(part)
                                part.add_header(
                                    'Content-Disposition',
                                    f'attachment; filename={os.path.basename(file_path)}'
                                )
                                message.attach(part)
                        except Exception as e:
                            return {"success": False, "error": f"Error attaching file {file_path}: {str(e)}"}
                
                # Encode the message
                encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
                
                # Create the message body
                create_message = {'raw': encoded_message}
                
                # Send the email
                sent_message = service.users().messages().send(
                    userId='me', 
                    body=create_message
                ).execute()
                
                return {"success": True, "message_id": sent_message['id']}
                
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        @self.Server.tool()
        async def read_linkedin_pdf(pdf_path: str) -> dict:
            """
            Read the linked in profile pdf
            Args:
                pdf_path: Profile pdf path
            """
            try:
                path = Path(pdf_path)
                if not path.is_file():
                    return {"success": False, "error": f"PDF not found at: {path}"}
                
                reader = PdfReader(path)
                text_chunks: list[str] = []
                
                for page in reader.pages:
                    page_text = page.extract_text() or ""
                    text_chunks.append(page_text)
                
                content = "\n\n".join(text_chunks).strip()
                return {"success": True, "content": content}
            except Exception as e:
                return {"success": False, "error": f"Error reading PDF: {str(e)}"}