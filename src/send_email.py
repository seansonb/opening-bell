import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

def send_digest_email(digest_content, recipient_email=None):
    """
    Send the daily digest via email
    
    Args:
        digest_content: String containing the full digest
        recipient_email: Optional email override (defaults to env variable)
    """
    
    # Email configuration from environment variables
    sender_email = os.getenv('SENDER_EMAIL')
    sender_password = os.getenv('SENDER_PASSWORD')
    recipient = recipient_email or os.getenv('RECIPIENT_EMAIL', sender_email)
    
    if not sender_email or not sender_password:
        raise ValueError("SENDER_EMAIL and SENDER_PASSWORD must be set in .env file")
    
    # Create message
    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"Daily Stock Digest - {datetime.now().strftime('%B %d, %Y')}"
    msg['From'] = sender_email
    msg['To'] = recipient
    
    # Convert markdown-style formatting to HTML
    html_content = markdown_to_html(digest_content)
    
    # Attach both plain text and HTML versions
    text_part = MIMEText(digest_content, 'plain')
    html_part = MIMEText(html_content, 'html')
    
    msg.attach(text_part)
    msg.attach(html_part)
    
    try:
        # Connect to Gmail's SMTP server
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, sender_password)
            server.send_message(msg)
        
        print(f"✓ Digest email sent successfully to {recipient}")
        return True
    
    except Exception as e:
        print(f"✗ Error sending email: {e}")
        return False

def markdown_to_html(content):
    """
    Simple markdown to HTML converter for email formatting
    """
    html = content
    
    # Convert headers
    html = html.replace('# ', '<h1>').replace('\n\n', '</h1>\n\n', 1)
    
    # Convert bold
    import re
    html = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', html)
    
    # Convert line breaks and separators
    html = html.replace('\n\n', '<br><br>')
    html = html.replace('=' * 60, '<hr>')
    html = html.replace('-' * 60, '<hr style="border: 1px dashed #ccc;">')
    
    # Wrap in HTML template
    html_template = f"""
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 800px; margin: 0 auto; padding: 20px; }}
            h1 {{ color: #2c3e50; border-bottom: 3px solid #3498db; padding-bottom: 10px; }}
            strong {{ color: #2c3e50; }}
            hr {{ border: 2px solid #3498db; margin: 20px 0; }}
        </style>
    </head>
    <body>
        {html}
    </body>
    </html>
    """
    
    return html_template

if __name__ == "__main__":
    # Test email sending
    test_digest = """# Daily Stock Digest - November 19, 2025

============================================================

**Apple Inc. (AAPL)**: $150.23 (+1.5%)

Apple announced new product updates today. The stock rose on positive market sentiment.

------------------------------------------------------------

**Microsoft Corporation (MSFT)**: $380.45 (-0.8%)

Microsoft reported quarterly earnings that slightly missed expectations.

------------------------------------------------------------
"""
    
    print("Sending test email...")
    send_digest_email(test_digest)