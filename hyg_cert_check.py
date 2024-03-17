"""Module providing a list of foodsavers missing the hygiene certificate for the next period."""

import sys
import io
import requests
import pyexcel_ods3

def penny_or_rewe(store):
    """Function to check if a store is 'penny' or 'rewe' based on the name"""
    name_lower = store['name'].lower()
    return 'penny' in name_lower or 'rewe' in name_lower

def login(email, password):
    """Function to login to foodsharing api"""
    session = requests.Session()
    data = {"email": email, "password": password, "remember_me": 'True'}
    response = session.post('https://foodsharing.de/api/user/login', json=data)

    if 200 == response.status_code:
        user = session.get('https://foodsharing.de/api/user/current/details').json()
        firstname = user['firstname']
        lastname = user['lastname']
        fsid = user['id']
        print(f'Logged in as: {firstname} {lastname} ({fsid})')
    else:
        print('Login failed - verify username and password')

    return session

def get_cert_list(session, password):
    """Function to get the hygiene certificate list"""
    headers = { 'X-Requested-With': 'XMLHttpRequest', }
    response = session.get('https://cloud.foodsharing.network/public.php/webdav',
                        headers=headers,
                        auth=('i3k4cks9P9WirYR', password))

    file = pyexcel_ods3.get_data(io.BytesIO(response.content))

    list_cert = []
    table = file['Tabelle1']
    header = table[0]

    for row in table[1:]:
        cert_list_entry = ['' for _ in range(len(header))]
        for i, value in enumerate(row):
            cert_list_entry[i] = value
        list_cert.append(cert_list_entry)

    return header, list_cert

def get_store_list(session):
    """Function to get the penny or rewe stores managed by the logged in foodsharing user"""
    stores = session.get('https://foodsharing.de/api/user/current/stores').json()

    stores_managed = [store for store in stores if 'isManaging' in store and store['isManaging']]
    stores_managed_certificate = [store for store in stores_managed if penny_or_rewe(store)]

    return stores_managed_certificate

def get_active_member(session, store_id):
    """Function to get the active members of a store"""
    store_members = session.get(f'https://foodsharing.de/api/stores/{store_id}/member').json()

    store_members_active = []
    for store_member in store_members:
        if store_member['team_active'] == 1:
            store_members_active.append(store_member)

    return store_members_active

def main():
    """Main function"""
    session = login(sys.argv[1], sys.argv[2])
    header, cert_list = get_cert_list(session, sys.argv[3])
    store_list = get_store_list(session)

    if 0 == len(store_list):
        print('Oh, it looks like you do not manage stores like '
              'Penny or Rewe that require hygiene certificates.')
        return

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

                #clearn fsid from cerificate list from special characters
                fsid = cert[1]
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

    print('Keep in mind, this only checks Pennys and Rewes you manage')

if __name__ == "__main__":
    main()
