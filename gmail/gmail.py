from __future__ import print_function
import httplib2
import os
import re
from fuzzywuzzy import process
from apiclient import discovery
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


email_list = []

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
                headers = self.service.users().messages().get(userId=self.user_id, id=message_id['id']).execute()['payload']['headers']
                for header in headers:
                    if header['name'] == 'From':
                        try:
                            email_from = (re.findall(r'(<.*>)', header['value'])[0].replace("<", "").replace(">", ""))
                        except IndexError:
                            email_from = (header['value'])

                        email_list.append(email_from)
        


SCOPES = 'https://www.googleapis.com/auth/gmail.readonly'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Gmail API Python Quickstart'


def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'gmail-python-quickstart.json')

    store = oauth2client.file.Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatability with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials


def main():
    """Shows basic usage of the Gmail API.

    Creates a Gmail API service object and outputs a list of label names
    of the user's Gmail account.
    """

    parser = argparse.ArgumentParser('gmail')
    parser.add_argument('--query',
                        help=('Queries you want to for for gmail.'))
    parser.add_argument('--output',
                        help=('which style of output. '
                              '(default: %(default)s)'),
                        choices=['table', 'csv'], default='table')
    parser.add_argument('--file-name', 
                        help=('Whad do you want to name the output file. '
                              '(default: %(default)s))'),
                        default='emails.csv')
    args = parser.parse_args()


    email_counted = []
    columns = ["Email", "Count", "Action"]
    
    if args.output == 'csv':
        writer = CsvOutputWriter(columns, args.file_name)
    else:
        writer = TableOutputWriter(columns)

    user_id = 'me'
    query = args.query
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)

    messages_response = service.users().messages().list(userId=user_id,q=query).execute()

    thread_list = []
    if 'messages' in messages_response:
        thread = appendList(user_id, messages_response['messages'])
        thread_list.append(thread)
        thread.start()

    while 'nextPageToken' in messages_response:
        page_token = messages_response['nextPageToken']
        messages_response = service.users().messages().list(userId=user_id,q=query,pageToken=page_token).execute()
        thread = appendList(user_id, messages_response['messages'])
        thread_list.append(thread)
        thread.start()

    for t in thread_list:
    #     t.join()
        while t.isAlive():
            print ('Checking email #' + str(len(email_list)+1), end='')
            print ('\r', end='')
            sys.stdout.flush()

    test = collections.Counter(email_list)
    for entry in test.keys():
        writer.write(entry, test[entry], '')

    writer.flush()
    print ('Total emails found: ' + str(len(email_list)))

if __name__ == '__main__':
    main()