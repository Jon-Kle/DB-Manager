import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_warning()
    # check error type
    # get text
    # +?
    # assemble email message
    # join address list to a string [a@example.com, b@example.com, c@...]

def send_resolution()

def send_email(message: MIMEMultipart, receiver_email):
    host = "" # get host from file
    port = ""
    sender_email = ""
    password = ""
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email, message.as_string())