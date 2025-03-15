import os
import email
import base64

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.modify']
NEWLINE = "\n"
DIRPATH = "abstracts_filtered"
LABELID = "Label_7139621076713114511"


def check_credentials():
    """
    Check credentials and save for the next session
    """

    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except:
                os.remove('token.json')
                e = "Auth error. Removed token.json. Please, run the script"
                e += " again"
                input(e)
                raise
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    return creds


def grab_subject_body(message):
    """
    Extract the subject and body of the message
    """

    # Get the message object
    payload = message["payload"]

    # Grab the subject
    subject = None
    for line in payload["headers"]:
        if line["name"] == "Subject":
            subject = line["value"]

    # And the body
    if "parts" in payload:
        try:
            body = payload["parts"][0]["body"]["data"]
        except:
            return None, None
        encoding = "utf-8"
    else:
        body = payload["body"]["data"]
        encoding = "ascii"

    body = base64.urlsafe_b64decode(body)
    body = email.message_from_bytes(body).as_string()

    return subject, body


def get_abstracts_links(body, keywords):
    """
    Grab the abstracts and filter them from the body
    """

    # Search for abstracts in the e-mail
    abstracts = []
    links = []

    nOfSlashes = 0
    weWantAbstract = False
    abstract = ""
    for line in body.split(NEWLINE):

        if "\\\\" in line:

            # Check if we just went through an abstract
            if nOfSlashes == 0:
                # Reset abstract
                abstract = ""

                # Add one to the flag
                nOfSlashes += 1

            # If the flag is 2, we can save this
            elif nOfSlashes == 2:

                # Check if keywords in abstract
                weWantAbstract = False
                for keyword in keywords:
                    if keyword in abstract:
                        weWantAbstract = True
                        abstracts.append(abstract)
                        break

                # Reset the flag
                nOfSlashes = 0
            else:
                # Add one to the flag
                nOfSlashes += 1

            # Found the link, see if we want to save it
            if "http" in line:
                if weWantAbstract:
                    links.append(line)
                    weWantAbstract = False

        if nOfSlashes != 0:
            abstract += line + NEWLINE

            # If "replaced" in line, we will not find the third "//"
            # so we count one more
            if "replaced" in line:
                nOfSlashes += 1

    return abstracts, links


def write_to_file(subject, abstracts, links):
    """
    Write to file the filtered abstracts and links
    """

    # Skip if there is nothing to write
    if len(abstracts) == 0:
        return None

    path = os.path.join(DIRPATH, subject + ".txt")
    with open(path, "a") as fwrite:
        for abstract, link in zip(abstracts, links):
            fwrite.write(abstract)
            fwrite.write(link)
            fwrite.write(NEWLINE * 2 + "=" * 10 + NEWLINE)
            fwrite.write(NEWLINE * 2)


def main():
    """
    Filter the arxiv e-mails
    """

    creds = check_credentials()

    # Call the Gmail API
    try:
        service = build('gmail', 'v1', credentials=creds)
    except HttpError as error:
        print(f"Error ocurred while calling the API: {error}")

    # List the messages
    q = "is:unread"
    results = service.users().messages().list(userId='me', q=q).execute()

    # Now fetch the mesages information
    subCounter = 0
    for header in results["messages"]:
        id_ = header["id"]

        message = service.users().messages().get(userId="me", id=id_).execute()
        subject, body = grab_subject_body(message)
        if subject is None:
            continue

        if "math daily" not in subject and "astro-ph daily" not in subject:
            continue

        subject += f"_{subCounter}"
        subCounter += 1

        s = f"Dealing with message: {subject}"
        print(s)

        # Filter the abstracts and links
        if "astro-ph" in subject:
            keywords = ["AGB", "nucleosynthesis"]
            abstracts, links = get_abstracts_links(body, keywords)
            write_to_file(subject, abstracts, links)
        elif "math" in subject:
            keywords = ["explicit", "patankar"]
            abstracts, links = get_abstracts_links(body, keywords)
            write_to_file(subject, abstracts, links)

        labelIds = {"addLabelIds": [LABELID], "removeLabelIds": ["UNREAD"]}
        request = service.users().messages().modify(userId="me", id=id_,
                                                    body=labelIds)
        request.execute()


if __name__ == '__main__':
    main()
