"""Module providing a list of foodsavers missing the hygiene certificate for the next period."""

import sys
import io
import argparse
import requests
import pyexcel_ods3

CERT_LIST_COL_IDX_FS_ID = 1

def get_args():
    """Function to initialize argparse"""
    parser = argparse.ArgumentParser(description='Hygiene Certificate Checker')

    parser.add_argument('email', type=str,
                        help='Login email for your foodsharing account')
    parser.add_argument('login_password', type=str,
                        help='Login password for your foodsharing account')
    parser.add_argument('file_password', type=str,
                        help='Password for the hygiene certificate list')
    parser.add_argument('-V', '--version', action='version', version='%(prog)s 1.0',
                        help='Display version information')

    return parser.parse_args()


def penny_or_rewe(store):
    """Function to check if a store is 'penny' or 'rewe' based on the name"""
    name_lower = store['name'].lower()
    return 'penny' in name_lower or 'rewe' in name_lower

def login(email, password):
    """Function to login to foodsharing api"""
    session = requests.Session()
    data = {"email": email, "password": password, "remember_me": 'True'}
    response = session.post('https://foodsharing.de/api/user/login', json=data)

    if response.ok:
        response = session.get('https://foodsharing.de/api/user/current/details')

        if response.ok:
            user = response.json()
            print(f"Logged in as: {user['firstname']} {user['lastname']} ({user['id']})")
        else:
            print("Logged in as: failed to get user data")
    else:
        print('Error: Login failed - verify username and password')
        end_script()

    return session

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

def get_store_list(session):
    """Function to get the penny or rewe stores managed by the logged in foodsharing user"""
    response = session.get('https://foodsharing.de/api/user/current/stores')

    if not response.ok:
        print('Error: Failed to get your stores - please try again')
        end_script()

    stores = response.json()
    stores_managed = [store for store in stores if 'isManaging' in store and store['isManaging']]
    stores_managed_certificate = [store for store in stores_managed if penny_or_rewe(store)]

    return stores_managed_certificate

def get_active_member(session, store_id):
    """Function to get the active members of a store"""
    store_members_active = []

    response = session.get(f'https://foodsharing.de/api/stores/{store_id}/member')

    if response.ok:
        store_members = response.json()
        for store_member in store_members:
            if store_member['team_active'] == 1:
                store_members_active.append(store_member)
    else:
        print('Error: Failed to get the list of members  - please try again')

    return store_members_active

def check_cert(session, header, cert_list, store_list):
    """Function to check the certificate for all active FS in the handed over store list"""
    check_column_title = header[len(header) - 1]
    print(f'Certificates checked for: {check_column_title}\n')

    for store in store_list:
        print('----------------------------------')
        print(store['name'])
        print('----------------------------------')

        members = get_active_member(session, store['id'])
        for store_member_active in members:

            cert_valid = False
            in_list = False

            #compare active foodsaver with certificate list by id
            for cert in cert_list:

                #clean fsid in cerificate list from special characters
                fsid = cert[CERT_LIST_COL_IDX_FS_ID]
                if not isinstance(fsid, int):
                    fsid = ''.join(e for e in fsid if e.isalnum())
                    if fsid != '':
                        fsid = int(fsid)

                if store_member_active['id'] == fsid:
                    in_list = True
                    if '' != cert[len(header) - 1]:
                        cert_valid = True
                    break

            name = store_member_active['name']
            fsid = store_member_active['id']
            if not in_list:
                print(f'{name} ({fsid}) - not in list')
            elif not cert_valid:
                print(f'{name} ({fsid}) - old certificate')

        print('\n')

    print('Keep in mind, this checks Penny and Rewe stores you manage only')

def end_script():
    """Function to end the script"""
    input("\nPress Enter to exit...")
    sys.exit(1)

def main():
    """Main function"""
    try:
        args = get_args()
    except SystemExit:
        end_script()

    session = login(args.email, args.login_password)
    header, cert_list = get_cert_list(session, args.file_password)
    store_list = get_store_list(session)

    if 0 == len(store_list):
        print('Oh, it looks like you do not manage stores (Penny '
              'or Rewe) which require hygiene certificates.')
        end_script()

    check_cert(session, header, cert_list, store_list)
    end_script()

if __name__ == "__main__":
    main()
