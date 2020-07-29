from __future__ import print_function
import httplib2
import os
import re
# from fuzzywuzzy import process
# from apiclient import discovery
# from apiclient import errors
import base64
import email
import collections
import time
import csv
from prettytable import PrettyTable
import sys
import signal
import argparse
import threading
import sys
import pickle
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

#*********************************************
# Current Issues
#   - Thread exception when reading ALL emails
#   - No warning when no parameters are specified
#   - Custom labels will have issues with finding them.
# Nice to have
#   - Comments
#   - Cleaner code
#   - Creat a label if given doesn't exists
# Documentation
#   - SPAM label wont delete
#   - Default Labels
#   - How to mark action in the file
#   - queries example
# Ideas
#   - if count only list, then don't include message_id and query for all data
#*********************************************

email_list = []
label_map = {}

class Email_Object:
    def __init__(self, message_id, email_from, subject):
        self.message_id = message_id
        self.email_from = email_from
        self.subject = subject

class OutputWriter(object):
    def write(self, *row):
        pass

    def flush(self):
        pass

class TableOutputWriter(OutputWriter):
    def __init__(self, columns, align=None):
        align = align or {}

        self.table = PrettyTable(columns)
        self.table.align = align.get('*', 'l')

        for column, alignment in align.items():
            self.table.align[column] = alignment

    def write(self, *row):
        self.table.add_row(row)

    def flush(self):
        print(self.table)

class CsvOutputWriter(OutputWriter):
    def __init__(self, columns, fileName):
        self.file = open(fileName, 'w')
        self.writer = csv.writer(self.file, delimiter=',')
        self.writer.writerow(columns)

    def write(self, *row):
        self.writer.writerow(row)

    def flush(self):
        print(self.file.name + ' written.')
        self.file.close()

class processEmails (threading.Thread):
    def __init__(self, user_id, message_list):
        threading.Thread.__init__(self)
        self.user_id = user_id
        # Each thread has its own service so it doesn't interfere with others.
        self.service = service = build('gmail', 'v1', credentials=get_credentials())
        self.message_list = message_list
    
    def run(self):
        global email_list

        if self.message_list:
            for message_id in self.message_list:
                try:
                    headers = self.service.users().messages().get(userId=self.user_id, id=message_id['id']).execute()['payload']['headers']
                    from_who = None
                    email_sub = None
                    for header in headers:
                        if header['name'] == 'From':
                            try:
                                from_who = (re.findall(r'(<.*>)', header['value'])[0].replace("<", "").replace(">", ""))
                            except IndexError:
                                from_who = (header['value'])

                        if header['name'] == 'Subject':
                            email_sub = (header['value'])
                    try:
                        if from_who and email_sub:
                            email_list.append(Email_Object(message_id['id'], from_who, email_sub))
                        elif from_who:
                            email_list.append(Email_Object(message_id['id'], from_who, ''))
                        elif email_sub:
                            email_list.append(Email_Object(message_id['id'], '', email_sub))
                    except KeyError as err:
                        print ("Issue with message ID: " + message_id['id'])
                        print ('Error: %s' % err)
                except KeyError as error:
                    print('Issue with message ID: ' + message_id['id'])
                    print('Error: %s' % error)
                
        
def create_msg_labels(add_list, remove_list):
  """Create object to update labels.
  Args:
    add_list: List of labels that needs to be applied to a message
    remove_list: List of labels that needs to be removed from a message

  Returns:
    A label update object.
  """
  return {'addLabelIds': add_list, 'removeLabelIds': remove_list}

def modify_message_labels(service, user_id, msg_id, msg_labels):
  """Modify the Labels on the given Message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me" can be used to indicate the authenticated user.
    msg_id: The id of the message required.
    msg_labels: The change in labels.

  Returns:
    Modified message, containing updated labelIds, id and threadId.
  """
  try:
    message = service.users().messages().modify(userId=user_id, id=msg_id, body=msg_labels).execute()

    print ('Label changes for message with id ' + msg_id + ': %s' % msg_labels)

    return message
  except HttpError as error:
    print ('An error occurred: %s' % error)


def delete_message(service, user_id, message_id):
  """Delete a Message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me" can be used to indicate the authenticated user.
    msg_id: ID of Message to delete.
  """
  try:
    service.users().messages().delete(userId=user_id, id=message_id).execute()
    print ('Message with id: %s deleted successfully.' % message_id)
  except HttpError as error:
    print ('An error occurred: %s' % error)

def create_label_mapping(service, user_id):
    """Create a map of label names to label id that google recognizes 
    Args:
        service: Authorized Gmail API service instance.
        user_id: User's email address. The special "me"
        can be used to indicate the authenticated user.
    """
    results = service.users().labels().list(userId=user_id).execute()
    labels = results.get('labels', [])
    if not labels:
        print('No labels found.')
    else:
      for label in labels:
        label_map[label['name']] = label['id']

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    creds = None
    # The file token.pickle stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    if os.path.exists('token.pickle'):
        with open('token.pickle', 'rb') as token:
            creds = pickle.load(token)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open('token.pickle', 'wb') as token:
            pickle.dump(creds, token)

    return creds


def main():
    """Accessing your Gmail via script.
    You can do varaiety of things.
    """

    parser = argparse.ArgumentParser('gmail')
    parser.add_argument('--query',
                        help=('Queries you want to for for gmail.'),
                        default='')
    parser.add_argument('--output',
                        help=('which style of output. '
                              '(default: %(default)s)'),
                        choices=['table', 'csv'], default='table')
    parser.add_argument('--file-name', 
                        help=('Whad do you want to name the output file. '
                              '(default: %(default)s))'),
                        default='emails.csv')
    parser.add_argument('--include-subject',
                        action='store_true',
                        dest='include_subject',
                        help=('Include subject in output.'),
                        default=False)
    parser.add_argument('--read-file',
                        help=('Read file with email actions attached. '
                              '(must be a csv file created by this program default: %(default)s))'))
    args = parser.parse_args()

    email_counted = []
    user_id = 'me'
    service = build('gmail', 'v1', credentials=get_credentials())
    input_file = ''
    columns = ["Message ID", "Email", "Count"]

    create_label_mapping(service, user_id)

    if args.include_subject:
        columns.append('Subject')
        columns.remove('Count')
    else:
        columns.remove('Message ID')

    if args.read_file:
        print ('read file: %s' % args.read_file)
        readFile=csv.reader(open(args.read_file,'rU'), delimiter=',')
        add_label_list = []
        remove_label_list = []
        subject_included = False
        counter = 0
        for line in readFile:
            counter += 1
            if 'Subject' in line:
                subject_included=True 
                continue
            print ("Processing line: %s " % counter)
            if subject_included:
                message_id=line[0]
                email=line[1]
                subject=line[2]
                action=line[3]
            else:
                email=line[0]
                action=line[2]
                
            if action == 'delete':
                delete_message(service, user_id, message_id)
            elif 'label' in action:
                for label_action in action.split(';'):
                    if 'add-label' in label_action:
                        for user_label in label_action.split(':')[1].split(' '):
                            add_label_list.append(label_map[user_label]) 
                    if 'remove-label' in label_action:
                        for user_label in label_action.split(':')[1].split(' '):
                            remove_label_list.append(label_map[user_label]) 
                modify_message_labels(service, user_id, message_id, create_msg_labels(add_label_list, remove_label_list))
            else:
                print('No action specified for:')
                print(' email: ' + email)
                print(' subject: ' + subject)
                print('') #Visual presentation
            print ("")
    else:
        if args.output == 'csv':
            writer = CsvOutputWriter(columns, args.file_name)
        else:
            writer = TableOutputWriter(columns)

        messages_response = service.users().messages().list(userId=user_id,q=args.query).execute()

        thread_list = []
        if 'messages' in messages_response:
            message_id_list = messages_response['messages']
            thread = processEmails(user_id, message_id_list)
            thread.daemon = True
            thread_list.append(thread)
            thread.start()

        while 'nextPageToken' in messages_response:
            page_token = messages_response['nextPageToken']
            messages_response = service.users().messages().list(userId=user_id,q=args.query,pageToken=page_token).execute()
            if 'messages' in messages_response:
                message_id_list = messages_response['messages']
                thread = processEmails(user_id, message_id_list)
                thread.daemon = True
                thread_list.append(thread)
                thread.start()

        thread_done_counter = 0
        
        while threading.active_count() != 1:
            try:
                print('Total threads done %s out of %s' % (len(thread_list) - (threading.active_count() - 1), len(thread_list)))
                time.sleep(1)
            except KeyboardInterrupt:
                print ("\nGoodbye!")
                sys.exit() # Kill all threads
        print('Total threads done %s out of %s' % (len(thread_list) - (threading.active_count() - 1), len(thread_list)))

        if args.include_subject:
            for entry in email_list:
                writer.write(entry.message_id, entry.email_from, entry.subject.encode('utf-8','ignore'))
        else:
            counted_emails = collections.Counter(i.email_from for i in email_list)
            for entry in counted_emails.keys():
                writer.write(entry, counted_emails[entry])

        writer.flush()
        print ('Total emails found: ' + str(len(email_list)))

if __name__ == '__main__':
    main()