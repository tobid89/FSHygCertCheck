"""Module providing a list of foodsavers missing the hygiene certificate for the next period."""

import sys
import io
import argparse
import requests
import pyexcel_ods3

TEAM_MEMBER_TYPE_ACTIVE = 1
TEAM_MEMBER_TYPE_JUMPER = 2

VERSION = '1.1'
VERSION_HISTORY = """\
1.1
- Adjust for release „Laugenbrezel“ (April 2024)
- Check jumper for valid certificate 
1.0
- Initial version - broken since release „Laugenbrezel“ (April 2024)\
"""

class VersionHistoryAction(argparse.Action):
    """Class used for the version history"""
    def __call__(self, parser, namespace, values, option_string=None):
        print(f'Version {VERSION}\n')
        print("Version History:")
        print(VERSION_HISTORY)
        parser.exit()

def get_args():
    """Function to initialize argparse"""
    parser = argparse.ArgumentParser(description='Hygiene Certificate Checker')

    parser.add_argument('email', type=str,
                        help='Login email for your foodsharing account')
    parser.add_argument('login_password', type=str,
                        help='Login password for your foodsharing account')
    parser.add_argument('file_password', type=str,
                        help='Password for the hygiene certificate list')
    parser.add_argument('-V', '--version', action=VersionHistoryAction,
                        nargs=0, help="Display version history")

    return parser.parse_args()


def needs_hyg_cert(store):
    """Function to check if a store is 'penny', 'rewe' or 'aldi' based on the name"""
    name_lower = store['name'].lower()
    return 'penny' in name_lower or 'rewe' in name_lower or 'aldi' in name_lower

def login(email, password):
    """Function to login to foodsharing api"""
    fs_id = 0
    session = requests.Session()
    data = {"email": email, "password": password, "remember_me": 'True'}
    response = session.post('https://foodsharing.de/api/user/login', json=data)

    if response.ok:
        response = session.get('https://foodsharing.de/api/user/current/details')

        if response.ok:
            user = response.json()
            fs_id = user['id']
            print(f"Logged in as: {user['firstname']} {user['lastname']} ({fs_id})")
        else:
            print("Logged in as: failed to get user data")
    else:
        print('Error: Login failed - verify username and password')
        end_script()

    return session, fs_id

def get_cert_list(session, password):
    """Function to get the hygiene certificate list"""
    headers = { 'X-Requested-With': 'XMLHttpRequest', }
    response = session.get('https://cloud.foodsharing.network/public.php/webdav',
                           headers=headers,
                           auth=('i3k4cks9P9WirYR', password))

    if not response.ok:
        print('Error: Failed to get certificate list - verify file password')
        end_script()

    file = pyexcel_ods3.get_data(io.BytesIO(response.content))

    cert_list = []
    table = file['Tabelle1']
    header = table[0]

    #pyexcel removes empty entries at the end, this created a list with a defined column count
    for row in table[1:]:
        cert_list_entry = ['' for _ in range(len(header))]
        for i, value in enumerate(row):
            cert_list_entry[i] = value
        cert_list.append(cert_list_entry)

    return header, cert_list

def get_store_list(session, fs_id):
    """Function to get the penny or rewe stores managed by the logged in foodsharing user"""
    response = session.get(f'https://foodsharing.de/api/user/{fs_id}/stores')

    if not response.ok:
        print('Error: Failed to get your stores - please try again')
        end_script()

    stores = response.json()
    stores_managed = [store for store in stores if 'isManaging' in store and store['isManaging']]
    stores_managed_certificate = [store for store in stores_managed if needs_hyg_cert(store)]

    return stores_managed_certificate

def get_member(session, store_id, member_type):
    """Function to get the active members of a store"""
    store_members_active = []

    response = session.get(f'https://foodsharing.de/api/stores/{store_id}/member')

    if response.ok:
        store_members = response.json()
        for store_member in store_members:
            if store_member['team_active'] == member_type:
                store_members_active.append(store_member)
    else:
        print('Error: Failed to get the list of members  - please try again')

    return store_members_active

def check_cert(store_member, cert_list, fs_id_column_index, cert_colum_index):
    """Function to check the certificate for a store member"""
    cert_valid = False
    in_list = False

    #compare active foodsaver with certificate list by id
    for cert in cert_list:

        #clean fsid in cerificate list from special characters
        fsid = cert[fs_id_column_index]
        if not isinstance(fsid, int):
            fsid = ''.join(e for e in fsid if e.isalnum())
            if fsid != '':
                fsid = int(fsid)

        if store_member['id'] == fsid:
            in_list = True
            if '' != cert[cert_colum_index]:
                cert_valid = True
            break

    return store_member['id'], store_member['name'], in_list, cert_valid

def check_cert_for_store_list(session, header, cert_list, store_list):
    """Function to check the certificate for all active FS in the handed over store list"""
    fs_id_column_index = header.index("FS-ID")
    cert_colum_index = len(header) - 1
    check_column_title = header[cert_colum_index]
    print(f'Certificates checked for: {check_column_title}\n')

    for store in store_list:
        print('----------------------------------')
        print(store['name'])
        print('----------------------------------')
        print('Active FS without valid certificate:')
        members = get_member(session, store['id'], TEAM_MEMBER_TYPE_ACTIVE)
        for store_member_active in members:
            fs_id, name, in_list, cert_valid = check_cert(store_member_active,
                                                          cert_list,
                                                          fs_id_column_index,
                                                          cert_colum_index)

            if not in_list:
                print(f'  {name} ({fs_id}) - not in list')
            elif not cert_valid:
                print(f'  {name} ({fs_id}) - old certificate')

        print('\nJumper FS with valid certificate:')
        members = get_member(session, store['id'], TEAM_MEMBER_TYPE_JUMPER)
        for store_member_jumper in members:
            fs_id, name, in_list, cert_valid = check_cert(store_member_jumper,
                                                          cert_list,
                                                          fs_id_column_index,
                                                          cert_colum_index)
            if cert_valid:
                print(f'  {name} ({fs_id}) - valid certificate')

        print('\n')

    print('Keep in mind, this checks Penny, Rewe & Aldi stores you manage only')

def end_script():
    """Function to end the script"""
    input("\nPress Enter to exit...")
    sys.exit(0)

def main():
    """Main function"""
    try:
        args = get_args()
    except SystemExit:
        end_script()

    session, fs_id = login(args.email, args.login_password)
    header, cert_list = get_cert_list(session, args.file_password)
    store_list = get_store_list(session, fs_id)

    if 0 == len(store_list):
        print('Oh, it looks like you do not manage stores (Penny '
              'or Rewe) which require hygiene certificates.')
        end_script()

    check_cert_for_store_list(session, header, cert_list, store_list)
    end_script()

if __name__ == "__main__":
    main()
