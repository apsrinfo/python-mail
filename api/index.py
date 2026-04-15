import smtplib
import socks
import socket
import time
import threading
import re
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
#dipanshu
# Global variable to store current proxy settings
current_proxy = None

# Function to set proxy dynamically
def set_proxy(proxy_ip, proxy_port):
    socks.set_default_proxy(socks.SOCKS5, proxy_ip, proxy_port)  # Use SOCKS5 proxy
    socket.socket = socks.socksocket  # Apply proxy settings to the socket
#dipanshu verma ji mailer 
# Function to validate email address
def is_valid_email(email):
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

# Function to add SPF, DKIM, and DMARC instructions for the user
def print_authentication_instructions():
    print("\nSet up the following DNS records for your domain:")
    print("SPF Record:")
    print("v=spf1 include:_spf.google.com ~all")
    print("\nDKIM Key:")
    print("Generate this from your email provider and add it as a TXT record in DNS.")
    print("\nDMARC Record:")
    print("v=DMARC1; p=none;")

# Function to send email
def send_single_email(sender_email, app_password, recipient_email, sender_name, subject, template_content):
    try:
        # Setup the SMTP server connection
        server = smtplib.SMTP_SSL('smtp.gmail.com', 465)
        server.login(sender_email, app_password)  # Use sender email and app password to login

        # Extract recipient name (optional)
        name = recipient_email.split('@')[0]

        msg = MIMEMultipart()
        msg['From'] = f"{sender_name} <{sender_email}>"
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Replace placeholders in the template
        body = template_content.replace("[SenderName]", sender_name).replace("[RecipientName]", name)
        msg.attach(MIMEText(body, 'plain'))


        # Send the email
        server.sendmail(sender_email, recipient_email, msg.as_string())
        server.quit()
        print(f"Email sent successfully to {recipient_email}")
        return True

    except smtplib.SMTPException as e:
        print(f"SMTP error sending email to {recipient_email}: {str(e)}")
        return False
    except Exception as e:
        print(f"Error sending email to {recipient_email}: {str(e)}")
        return False

# Function to send emails in parallel with retries
def send_emails_with_retries(sender_email, app_password, recipient_emails, sender_name, subject, template_content, max_threads=10, max_retries=3):
    success_count = 0
    failure_count = 0
    lock = threading.Lock()
    retry_queue = []

    def worker(emails):
        nonlocal success_count, failure_count
        for recipient_email in emails:
            retries = 0
            while retries < max_retries:
                try:
                    if send_single_email(sender_email, app_password, recipient_email, sender_name, subject, template_content):
                        with lock:
                            success_count += 1
                        break
                    else:
                        raise Exception("Failed to send email")
                except Exception as e:
                    retries += 1
                    print(f"Retrying {recipient_email} ({retries}/{max_retries}) due to error: {str(e)}")
                    time.sleep(2)  # Delay before retry

            if retries == max_retries:
                with lock:
                    failure_count += 1
                    retry_queue.append(recipient_email)

    # Validate emails before sending
    valid_emails = [email for email in recipient_emails if is_valid_email(email)]
    invalid_emails = [email for email in recipient_emails if not is_valid_email(email)]

    print(f"Invalid emails skipped: {invalid_emails}")

    # Split recipient emails into chunks for threads
    chunk_size = max(1, len(valid_emails) // max_threads)
    threads = []
    for i in range(0, len(valid_emails), chunk_size):
        chunk = valid_emails[i:i + chunk_size]
        thread = threading.Thread(target=worker, args=(chunk,))
        threads.append(thread)
        thread.start()

    # Wait for all threads to finish
    for thread in threads:
        thread.join()

    return success_count, failure_count, retry_queue

# Route for the homepage
@app.route('/')
def index():
    return render_template('index.html')

# Route for sending emails
@app.route('/send_emails', methods=['POST'])
def send_email():
    sender_email = request.form.get('sender_email')  # Sender email
    app_password = request.form.get('app_password')  # App password

    if not sender_email or not app_password:
        return {"status": "error", "message": "Sender email or app password is missing"}

    recipient_emails = request.form.get('bulk_email').split('\n')  # Split recipients by newline
    recipient_emails = [email.strip() for email in recipient_emails if email.strip()]
    subject = request.form.get('subject')
    sender_name = request.form.get('sender_name')  # Sender's name
    template_content = request.form.get('template')  # Email template content

    # Limit total emails to 4546564
    max_emails = 7683783
    if len(recipient_emails) > max_emails:
        recipient_emails = recipient_emails[:max_emails]

    # Send emails with retries
    success_count, failure_count, retry_queue = send_emails_with_retries(
        sender_email, app_password, recipient_emails, sender_name, subject, template_content
    )

    return {
        "status": "success",
        "message": f"Emails sent successfully! Success: {success_count}, Failures: {failure_count}, Retries Left: {len(retry_queue)}",
        "invalid_emails": retry_queue
    }

if __name__ == '__main__':
    print_authentication_instructions()
    app.run(debug=True, host='0.0.0.0', port=5072)
