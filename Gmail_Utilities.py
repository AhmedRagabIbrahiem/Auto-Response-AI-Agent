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

# Define the Gmail API scope - Add send scope
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly', 
          'https://www.googleapis.com/auth/gmail.send']

def get_gmail_service():
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
            flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
            creds = flow.run_local_server(port=0)
        
        # Save credentials for next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)
    
    return build('gmail', 'v1', credentials=creds)

def get_latest_email():
    """Fetch the most recent email from Gmail"""
    service = get_gmail_service()
    
    # Get list of messages (maxResults=1 for the most recent)
    results = service.users().messages().list(
        userId='me', 
        maxResults=1
    ).execute()
    
    if 'messages' not in results:
        print("No messages found")
        return None
    
    # Get the most recent message
    message_id = results['messages'][0]['id']
    message = service.users().messages().get(
        userId='me', 
        id=message_id,
        format='full'
    ).execute()
    
    # Extract headers
    headers = message['payload']['headers']
    email_data = {}
    
    for header in headers:
        if header['name'] in ['Subject', 'From', 'Date']:
            email_data[header['name']] = header['value']
    
    # Get snippet (preview text)
    email_data['Snippet'] = message.get('snippet', '')
    
    return email_data

def send_email(to, subject, body, cc=None, bcc=None, attachments=None):
    """
    Send an email using Gmail API
    
    Args:
        to (str or list): Recipient email address(es)
        subject (str): Email subject
        body (str): Email body text
        cc (str or list, optional): CC recipient(s)
        bcc (str or list, optional): BCC recipient(s)
        attachments (list, optional): List of file paths to attach
    """
    service = get_gmail_service()
    
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
                print(f"Error attaching file {file_path}: {e}")
    
    # Encode the message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    # Create the message body
    create_message = {'raw': encoded_message}
    
    # Send the email
    try:
        # Get all recipients (to, cc, bcc) for the send operation
        all_recipients = to_list
        if cc:
            all_recipients.extend(cc_list if isinstance(cc, list) else [cc])
        if bcc:
            all_recipients.extend(bcc_list if isinstance(bcc, list) else [bcc])
        
        # Send the email
        sent_message = service.users().messages().send(
            userId='me', 
            body=create_message
        ).execute()
        
        print(f"Email sent successfully!")
        print(f"Message ID: {sent_message['id']}")
        return sent_message['id']
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return None

def send_html_email(to, subject, html_body, text_body=None, cc=None, bcc=None, attachments=None):
    """
    Send an HTML email using Gmail API
    
    Args:
        to (str or list): Recipient email address(es)
        subject (str): Email subject
        html_body (str): HTML email body
        text_body (str, optional): Plain text fallback
        cc (str or list, optional): CC recipient(s)
        bcc (str or list, optional): BCC recipient(s)
        attachments (list, optional): List of file paths to attach
    """
    service = get_gmail_service()
    
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
        # Simple HTML to text conversion (or use html2text library for better results)
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
                print(f"Error attaching file {file_path}: {e}")
    
    # Encode the message
    encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
    
    # Create the message body
    create_message = {'raw': encoded_message}
    
    # Send the email
    try:
        sent_message = service.users().messages().send(
            userId='me', 
            body=create_message
        ).execute()
        
        print(f"HTML email sent successfully!")
        print(f"Message ID: {sent_message['id']}")
        return sent_message['id']
        
    except Exception as e:
        print(f"Error sending email: {e}")
        return None

# Example usage
if __name__ == '__main__':
    # Example 1: Read latest email
    print("=== Reading Latest Email ===")
    email = get_latest_email()
    if email:
        print(f"From: {email.get('From')}")
        print(f"Subject: {email.get('Subject')}")
        print(f"Date: {email.get('Date')}")
        print(f"Preview: {email.get('Snippet')}")
    
    print("\n" + "="*50 + "\n")
    
    # Example 2: Send a simple text email
    print("=== Sending Text Email ===")
    send_email(
        to="recipient@example.com",
        subject="Test Email from Python",
        body="Hello! This is a test email sent using the Gmail API in Python.",
        cc="cc@example.com"  # Optional
    )
    
    # Example 3: Send an HTML email with attachment
    print("\n=== Sending HTML Email with Attachment ===")
    html_content = """
    <html>
        <body>
            <h1>Hello from Python!</h1>
            <p>This is a <b>test email</b> sent using the Gmail API.</p>
            <p>It supports HTML formatting!</p>
            <ul>
                <li>Bullet points</li>
                <li>Formatting</li>
                <li>Links: <a href="https://www.google.com">Google</a></li>
            </ul>
        </body>
    </html>
    """
    
    send_html_email(
        to="recipient@example.com",
        subject="HTML Email Test",
        html_body=html_content,
        text_body="Hello! This is a test email sent using the Gmail API.",  # Plain text fallback
        attachments=["test.txt"]  # Optional - make sure file exists
    )