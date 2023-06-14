'''
This module handles sending error messages and if they have been resolved per email (SMTP)

Functions
---------
send_warning(error: BaseException, debug=False):
        Sends a warn-email with the content adjusted to the specific error provided.
resolved(error_names: list):
        Sends a resolved-email regarding all errors provided in error_names 
        if these are currently active and thus can be resolved.
debug_email():
        A function for testing if everything works. Contains nothing.
send_email(message, subject, receiver_list):
        Send a mail with MIME content to the list of receivers provided by receiver_list.

'''

import json
import smtplib, ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from customExceptions import *
from logging import getLogger
from typing import List

def send_warning(error: BaseException, debug=False):
    '''
    Build and send a warn-email depending on the type of error given

            Parameters:
                    error (BaseException): the custom exception that occurred
                    debug (bool): decides if the error status gets changed and if the message number increments
    '''
    # read files and initiate logger
    log = getLogger('EMAIL MESSAGES')
    with open('res/warning-template.html') as f:
        html_template = f.read()
    with open('res/error_msg_config.json') as f:
        config_data = json.loads(f.read())

    # handle the status of the error
    if not debug: # activate error status
        if config_data['errors'][error_name]['active'] == True:
            log.info('aborting warn email: error already active')
            return # if the status of the error is active, don't send error message
        config_data['errors'][error_name]['active'] = True
        config_data['errors'][error_name]['count'] += 1
    else:
        log.info('sending debug warn email')

    # get future content of the email
    error_name = error.__class__.__name__
    error_number = config_data['errors'][error_name]['count']
    if debug:
        error_number = 'debugging'
    error_description = config_data['errors'][error_name]['text_de']['description']
    error_solution = config_data['errors'][error_name]['text_de']['suggested_solution']

    # optionally build list elements for the email
    optional_list = ''
    optional_warning = ['', '']
    if error_name == 'DataIncompleteError':
        optional_list = ''
        for m in error.missing:
            optional_list += f'<li>- {m}</li>'
        warning_list = config_data['errors']['DataIncompleteError']['text_de']['warning']
        optional_warning[0] = warning_list[0]
        optional_warning[1] = warning_list[1]
        
    # assemble the html message
    html_template = html_template.replace('{name}', f'{error_name} #{error_number}')
    html_template = html_template.replace('{description}', error_description)
    html_template = html_template.replace('{solution}', error_solution)
    html_template = html_template.replace('{opt_list}', optional_list)
    html_template = html_template.replace('{warning}', optional_warning[0])
    html_message = html_template.replace('{warning2}', optional_warning[1])

    # assemble the plain message
    plain_message = f""" --- Wetterstation Fehlermeldung ---

Name: {error_name} #{error_number}

Beschreibung: {error_description}

Lösungsvorschlag: {error_solution}
"""
    # assemble the email message
    message = MIMEMultipart('alternative')
    mime_text = MIMEText(plain_message, 'plain')
    mime_html = MIMEText(html_message, 'html')
    message.attach(mime_text)
    message.attach(mime_html)

    subject = f"{error_name} #{error_number}"
    email_list = config_data['errors'][error_name]['emails']

    # actual sending of the finished email
    try:
        send_email(message, subject, email_list)
    except BaseException as e:
        log.error('error message could not be sent: ' + str(e))
        print('Mail could not be sent:\n', e)
    else:
        log.info('error message sent')
        with open('res/error_msg_config.json', 'w') as f:
            f.write(json.dumps(config_data, indent='    '))

def resolved(error_names: List[str]):
    '''
    Send a resolved-email regarding all errors provided in error_names if these are currently active and thus can be resolved.
    Receivers are all the persons who receive messages for any of the resolved errors.

            Parameters:
                    error_names (List[str]): list of names of the resolved errors
    '''
    # read files and initiate logger
    log = getLogger('EMAIL MESSAGES')
    with open('res/warning-cancelation-template.html') as f:
        html_template = f.read()
    with open('res/error_msg_config.json') as f:
        config_data = json.loads(f.read())

    # get list of errors that have been resolved
    resolved_errors_message: List[str]= []
    resolved_errors_names: List[str] = []
    for n in error_names:
        if config_data['errors'][n]['active']:
            config_data['errors'][n]['active'] = False # deactivate them
            resolved_errors_message.append(f'{n} #{config_data["errors"][n]["count"]}')
            resolved_errors_names.append(n)
    if not resolved_errors_names:
        return
    # build list elements for message
    html_error_list = ''
    text_error_list = ''
    for r in resolved_errors_message:
        html_error_list += f'<li>- {r}</li>'
        text_error_list += f'- {r}\n'
    
    # assemble the html and plain text messages
    html_message = html_template.replace('{error_list}', html_error_list)
    plain_message = f""" --- Wetterstation Fehlermeldung behoben ---
    
    Folgende Fehler wurden behoben:
    {text_error_list}
    """

    # assemble the email message
    message = MIMEMultipart('alternative')
    mime_text = MIMEText(plain_message, 'plain')
    mime_html = MIMEText(html_message, 'html')
    message.attach(mime_text)
    message.attach(mime_html)
    
    subject = 'Fehler behoben: ' + ', '.join(resolved_errors_message)

    # create mail list from multiple lists
    email_list = set()
    for e in resolved_errors_names:
        new_emails = config_data['errors'][e]['emails']
        email_list.update(new_emails)
    email_list = list(email_list)
    
    # actual sending of the finished email
    try:
        send_email(message, subject, email_list)
    except BaseException as e:
        log.error('resolved message could not be sent: ' + str(e))
        print('resolved Mail could not be sent:\n', e)
    else:
        log.info('resolved message sent')
        with open('res/error_msg_config.json', 'w') as f:
            f.write(json.dumps(config_data, indent='    '))

def debug_email():
    '''This function does nothing unless a developer writes something in it.'''
    # error = DataIncompleteError()
    # error.missing = ['test1', 'test2', 'test3', 'test4']
    # send_warning(DBConnectionError(BaseException()), debug=True)
    # resolved(['DBConnectionError', 'DBWritingError'])
    ...

def send_email(message: MIMEMultipart, subject: str, receiver_list: list):
    '''
    Send an email with the given MIMEMultipart message with the given subject to all receivers in the given list

            Parameters:
                    message (MIMEMultipart): Message containing the html message as well as the plain text message which will be sent
                    subject (str): Subject of email
                    receiver_list (list): List of all receiver emails to which the email should be sent.
    '''
    # get all necessary config data
    with open('res/error_msg_config.json') as f:
        data = json.loads(f.read())['config']
        host = data['host']
        port = data['port']
        sender_email = data['user_email']
        password = data['password']

    # assemble string of all receivers
    receiver_email_str = ', '.join(receiver_list)
    
    # set final variables of the message
    message['Date'] = formatdate()
    message['Subject'] = subject
    message['To'] = receiver_email_str
    message['From'] = sender_email

    # actual connection with SMTP server and sending of email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(host, port, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(sender_email, receiver_email_str, message.as_string())