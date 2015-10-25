from __future__ import print_function
import httplib2
import os
import re
from fuzzywuzzy import process
from apiclient import discovery
from apiclient import errors
import oauth2client
from oauth2client import client
from oauth2client import tools
import base64
import email
import collections
import time
import csv
from prettytable import PrettyTable
import sys
import argparse
import threading
import sys

#*********************************************
# Current Issues
#   - Thread exception when reading ALL emails
#   - No warning when no parameters are specified
#   - Custom labels will have issues with finding them.
#   - disabled subject by default
# Nice to have
#   - Comments
#   - Cleaner code
# Documentation
#   - SPAM label wont delete
#   - Default Labels
#   - How to mark action in the file
# Ideas
#   - include_subject by default?
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

class appendList (threading.Thread):
    def __init__(self, user_id, message_list):
        threading.Thread.__init__(self)
        self.user_id = user_id
        self.service = discovery.build('gmail', 'v1', http=get_credentials().authorize(httplib2.Http()))
        self.message_list = message_list
    
    def run(self):
        global email_list

        if self.message_list:
            for message_id in self.message_list:
                # print("*********")
                # print(message_id['id'])
                headers = self.service.users().messages().get(userId=self.user_id, id=message_id['id']).execute()['payload']['headers']
                for header in headers:
                    # print(header)
                    if header['name'] == 'From':
                        try:
                            from_who = (re.findall(r'(<.*>)', header['value'])[0].replace("<", "").replace(">", ""))
                        except IndexError:
                            from_who = (header['value'])

                    if header['name'] == 'Subject':
                        email_sub = (header['value'])

                if from_who and email_sub:
                    email_list.append(Email_Object(message_id['id'], from_who, email_sub))
                elif from_who:
                    email_list.append(Email_Object(message_id['id'], from_who, ''))
                elif email_sub:
                    email_list.append(Email_Object(message_id['id'], '', email_sub))

                # print("*********")
        
def create_msg_labels(add_list, remove_list):
  """Create object to update labels.

  Returns:
    A label update object.
  """
  return {'addLabelIds': add_list, 'removeLabelIds': remove_list}

def modify_message_labels(service, user_id, msg_id, msg_labels):
  """Modify the Labels on the given Message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    msg_id: The id of the message required.
    msg_labels: The change in labels.

  Returns:
    Modified message, containing updated labelIds, id and threadId.
  """
  try:
    message = service.users().messages().modify(userId=user_id, id=msg_id,
                                                body=msg_labels).execute()

    print ('Label changes for message with id: %s: ' % msg_labels)

    return message
  except errors.HttpError, error:
    print ('An error occurred: %s' % error)


def delete_message(service, user_id, message_id):
  """Delete a Message.

  Args:
    service: Authorized Gmail API service instance.
    user_id: User's email address. The special value "me"
    can be used to indicate the authenticated user.
    msg_id: ID of Message to delete.
  """
  try:
    service.users().messages().delete(userId=user_id, id=message_id).execute()
    print ('Message with id: %s deleted successfully.' % message_id)
  except errors.HttpError, error:
    print ('An error occurred: %s' % error)

def create_label_mapping(service, user_id):
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
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    credential_path = os.path.join(credential_dir, 'gmail-tool.json')
    if not os.path.exists(credential_dir):
        print('Please run command \'python auth_gmail.py\' to create oauth token.')
        sys.exit()
    else:
        store = oauth2client.file.Storage(credential_path)
        credentials = store.get()
        if not credentials or credentials.invalid:
            print('Please run command \'python auth_gmail.py\' to recreate oauth token.')
            sys.exit()

    return credentials


def main():
    """Shows basic usage of the Gmail API.

    Creates a Gmail API service object and outputs a list of label names
    of the user's Gmail account.
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
                        help=('Include subject in output. '
                              '(default: %(default)s))'),
                        default='store_false')
    parser.add_argument('--read-file',
                        help=('Read file with email actions attached. '
                              '(must be a csv file created by this program default: %(default)s))'))
    args = parser.parse_args()


    email_counted = []
    user_id = 'me'
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)
    input_file = ''
    columns = ["Message ID", "Email", "Count", "Action"]

    create_label_mapping(service, user_id)

    if args.include_subject:
        columns.append('Subject')

    if args.read_file:
        print ('read file: %s' % args.read_file)
        readFile=csv.reader(open(args.read_file,'rU'), delimiter=',')
        
        for line in readFile:
            message_id=line[0]
            email=line[1]
            action=line[3]
            subject=line[4]
            add_label_list = []
            remove_label_list = []

            search_query = 'from:' + email + ' and subject:' + subject

            if email == "Email": #its the first line
                continue

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
    else:
        if args.output == 'csv':
            writer = CsvOutputWriter(columns, args.file_name)
        else:
            writer = TableOutputWriter(columns)

        messages_response = service.users().messages().list(userId=user_id,q=args.query).execute()

        thread_list = []
        if 'messages' in messages_response:
            thread = appendList(user_id, messages_response['messages'])
            thread_list.append(thread)
            thread.start()

        while 'nextPageToken' in messages_response:
            page_token = messages_response['nextPageToken']
            messages_response = service.users().messages().list(userId=user_id,q=args.query,pageToken=page_token).execute()
            thread = appendList(user_id, messages_response['messages'])
            thread_list.append(thread)
            thread.start()

        for t in thread_list:
            while t.isAlive():
                print ('Checking email #' + str(len(email_list)+1), end='')
                print ('\r', end='')
                sys.stdout.flush()

        if args.include_subject:
            for entry in email_list:
                writer.write(entry.message_id, entry.email_from, '1', '', entry.subject.encode('utf-8','ignore'))
        else:
            counted_emails = collections.Counter(i.email_from for i in email_list)
            for entry in counted_emails.keys():
                writer.write(entry, counted_emails[entry], '')

        writer.flush()
        print ('Total emails found: ' + str(len(email_list)))

if __name__ == '__main__':
    main()