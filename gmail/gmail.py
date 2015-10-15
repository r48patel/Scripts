#requirement.txt
#fuzzywuzzy
#googleAPI

from __future__ import print_function
import httplib2
import os
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
from apiclient import discovery
import oauth2client
from oauth2client import client
from oauth2client import tools
import base64
import email

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

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

    email_counted = {}

    user_id = 'me'
    query = 'label:Junk'
    # query = 'from:IKEA-USA@e.ikea-usa.com'
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('gmail', 'v1', http=http)

    messages_response = service.users().messages().list(userId=user_id,q=query).execute()

    messages = []
    if 'messages' in messages_response:
      messages.extend(messages_response['messages'])

    print (messages_response)

    while 'nextPageToken' in messages_response:
      page_token = messages_response['nextPageToken']
      messages_response = service.users().messages().list(userId=user_id,q=query,pageToken=page_token).execute()
      messages.extend(messages_response['messages'])

    if not messages:
        print ('No Emails found.')
    else:
        print ('Emails found')
        for message_id in messages:
            headers = service.users().messages().get(userId=user_id, id=message_id['id']).execute()['payload']['headers']
            headers_dict = {item for header in headers}
            findings = process.extract("From", headers, limit=5)
            print (findings)
            #print(header['value'] for header in headers if header['name'] == 'From')
            for header in headers:
                if header['name'] == 'From':
                    email_from = (header['value'])
                    print (email_from)
                    if email_from in email_counted:
                        count = email_counted[email_from];
                        email_counted[email_from] = count + 1
                    else:
                        email_counted[email_from] = 1

    for entry in email_counted:
        print (entry)

if __name__ == '__main__':
    main()