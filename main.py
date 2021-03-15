import csv
import config
import os
import random
import requests
import string
import sys

from bs4 import BeautifulSoup

from typing import List, Dict

BASE_PATH = os.path.dirname(os.path.abspath(__file__))

client = requests.Session()


def path(name: str, host=config.host) -> str:
    _path = {
        # Home
        'jury': '/jury',

        # Auth
        'login': '/login',

        # Users
        'user_list': '/jury/users',
        'user_add': '/jury/users/add',
        'user_edit': '/jury/users/{user_id}/edit',

        # Teams
        'team_list': '/jury/teams',
        'team_add': '/jury/teams/add',
    }

    assert name in _path, 'No path found.'

    return f'{host}{_path[name]}'


def load_users(filepath: str) -> List[Dict[str, str]]:
    assert os.path.exists(filepath), 'File not exists.'
    assert os.path.isfile(filepath), 'This is not a file.'

    with open(filepath, 'r') as f:
        data = list(csv.DictReader(f))

    return data


def save_users(filepath: str, users: List[Dict[str, str]]):
    if not users:
        return

    with open(filepath, 'w+') as f:
        writer = csv.DictWriter(f, fieldnames=users[0].keys())
        writer.writeheader()
        writer.writerows(users)


def gen_password(length=10):
    target = string.ascii_letters + string.digits
    return ''.join(random.choices(target, k=length))


def get_fields(page: str) -> dict:
    soup = BeautifulSoup(page, 'html.parser')

    data = {ele.get('name'): ele.get('value') for ele in soup.select('input')}

    select_tags = soup.select('select')
    for tag in select_tags:
        option = tag.select_one('option[selected]')
        data[tag.get('name')] = option.get('value') if option else None

    data.pop(None, None)  # remove no name fields
    return data


def login(username=config.username, password=config.password):
    res = client.get(path('login'))
    res.raise_for_status()

    data = {
        **get_fields(res.text),
        '_username': username,
        '_password': password,
    }

    res = client.post(path('login'), data=data)
    res.raise_for_status()

    assert res.url == path('jury'), 'Login fail.'


def create_team_and_user(user: dict):
    res = client.get(path('team_add'))
    res.raise_for_status()

    data = {
        **get_fields(res.text),
        'team[name]': user['std_no'],
        'team[displayName]': user['name'],
        'team[affiliation]': config.affiliation,
        'team[enabled]': config.enabled,
        'team[addUserForTeam]': '1',  # '1' -> Yes
        'team[users][0][username]': user['std_no'],
        'team[category]': config.category,
    }

    res = client.post(path('team_add'), data=data)
    res.raise_for_status()

    assert res.url != path('team_add'), 'Team create fail.'
    team_id = res.url.split('/')[-1]

    res = client.get(res.url)  # Go to team view page.
    res.raise_for_status()

    soup = BeautifulSoup(res.text, 'html.parser')
    user_link = soup.select_one('.container-fluid a')
    user_id = user_link['href'].split('/')[-1]

    return team_id, user_id


def set_user_password(user_id: str, password: str):
    url = path('user_edit').format(user_id=user_id)

    res = client.get(url)
    res.raise_for_status()

    data = {
        **get_fields(res.text),
        'user[plainPassword]': password,
        'user[enabled]': config.enabled,
        'user[user_roles][]': config.user_roles,
    }

    res = client.post(url, data=data)
    res.raise_for_status()

    assert res.url != url, 'User set password fail.'


def delete_users(exclude=('admin', 'judgehost')):
    res = client.get(path('user_list'))
    res.raise_for_status()

    soup = BeautifulSoup(res.text, 'html.parser')
    for row in soup.select('table tbody tr'):
        name = row.select('a')[0].text.strip()
        if name in exclude:
            continue

        link = row.select('a')[-1]['href']
        res = client.post(config.host + link)
        res.raise_for_status()


def delete_teams():
    res = client.get(path('team_list'))
    res.raise_for_status()

    soup = BeautifulSoup(res.text, 'html.parser')
    for row in soup.select('table tbody tr'):
        link = row.select('a')[-2]['href']
        res = client.post(config.host + link)
        res.raise_for_status()


def ask(text):
    return input(f'{text} [y/N]: ').lower() == 'y'


def main():
    login()

    if ask('Delete users'):
        delete_users()
        print('Delete users done.')
    else:
        print('Skip delete users')

    if ask('Delete teams'):
        delete_teams()
        print('Delete teams done.')
    else:
        print('Skip delete teams')

    assert len(sys.argv) >= 2, 'No file set.'

    filepath = sys.argv[1]
    data = load_users(filepath)

    print('Importing......')

    users = list()
    for datum in data:
        user = {**datum, 'password': gen_password()}
        team_id, user_id = create_team_and_user(user)
        set_user_password(user_id, user['password'])
        users.append(user)

    _out_filepath = filepath.split('.')
    _out_filepath.insert(-1, 'out')
    out_filepath = '.'.join(_out_filepath)
    save_users(out_filepath, users)

    print(f'Done file save at {out_filepath}.')


if __name__ == '__main__':
    main()
