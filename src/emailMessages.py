import json
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from customExceptions import *

def send_warning(error: BaseException, debug=False):
    with open('res/warning-template.html') as f:
        html_template = f.read()

    error_name = error.__class__.__name__

    with open('res/error_msg_config.json') as f:
        config_data = json.loads(f.read())

    if not debug:
        if config_data['errors'][error_name]['active'] == True:
            return # if the status of the error is active, don't send error message
        config_data['errors'][error_name]['active'] = True
        config_data['errors'][error_name]['count'] += 1

    error_number = config_data['errors'][error_name]['count']
    if debug:
        error_number = 'debugging'
    error_description = config_data['errors'][error_name]['text_de']['description']
    error_solution = config_data['errors'][error_name]['text_de']['suggested_solution']

    optional_list = ''
    optional_warning = ['', '']
    if error_name == 'DataIncompleteError':
        optional_list = ''
        for m in error.missing:
            optional_list += f'<li>- {m}</li>'
        warning_list = config_data['errors']['DataIncompleteError']['text_de']['warning']
        optional_warning[0] = warning_list[0]
        optional_warning[1] = warning_list[1]
        
    # assemble html message
    html_template = html_template.replace('{name}', f'{error_name} #{error_number}')
    html_template = html_template.replace('{description}', error_description)
    html_template = html_template.replace('{solution}', error_solution)
    html_template = html_template.replace('{opt_list}', optional_list)
    html_template = html_template.replace('{warning}', optional_warning[0])
    html_message = html_template.replace('{warning2}', optional_warning[1])

    # assemble plain message
    plain_message = f""" --- Wetterstation Fehlermeldung ---

Name: {error_name} #{error_number}

Beschreibung: {error_description}

Lösungsvorschlag: {error_solution}
"""
    # assemble email message
    message = MIMEMultipart('alternative')
    mime_text = MIMEText(plain_message, 'plain')
    mime_html = MIMEText(html_message, 'html')

    message.attach(mime_text)
    message.attach(mime_html)

    subject = f"Wetterstation Fehlermeldung: {error_name} #{error_number}"

    email_list = config_data['errors'][error_name]['emails']
    try:
        send_email(message, subject, email_list)
    except BaseException as e:
        print('Mail could not be sent:\n', e)
    else:
        with open('res/error_msg_config.json', 'w') as f:
            f.write(json.dumps(config_data, indent='    '))

def send_resolution(error_names: list):
    # read config file
    # go through list of error names
    # look if one or more of them are active
    # deactivate them
    # formulate message
    # list all Errors that are solved with name
    ...

def debug_email():
    error = DataIncompleteError()
    error.missing = ['test1', 'getestet2', 'getestinging3', 'and so on4']
    send_warning(DBConnectionError(BaseException()), debug=True)

def send_email(message: MIMEMultipart, subject: str, receiver_list: list):
    with open('res/error_msg_config.json') as f:
        data = json.loads(f.read())['config']
        host = data['host']
        port = data['port']
        sender_email = data['user_email']
        password = data['password']
    
    receiver_email_str = ', '.join(receiver_list)
    
    message['Date'] = formatdate()
    message['Subject'] = subject
    message['To'] = receiver_email_str
    message['From'] = sender_email

    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email_str, message.as_string())