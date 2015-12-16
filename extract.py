#!/usr/bin/env python3

import json
import os
import os.path as opath
import re
import soundcloud
import subprocess
import wget

from requests.exceptions import HTTPError
from subprocess import CalledProcessError

from pprint import pprint  # NOQA

DIR = opath.dirname(opath.realpath(__file__))
EXPORT = opath.join(DIR, 'export')

WHITESPACE = re.compile('\s')
NON_ALPHANUMERIC = re.compile('[^A-Za-z0-9_]')
MANY_UNDERSCORES = re.compile('_+')
FINAL_UNDERSCORES = re.compile('_+$')


def robotize(string):
    if string is None:
        return ''

    string = re.sub(WHITESPACE, '_', string)
    string = re.sub(NON_ALPHANUMERIC, '', string)
    string = re.sub(MANY_UNDERSCORES, '_', string)

    return string.lower()


def read_json_file(filename):
    with open(filename) as f:
        return json.loads(f.read())


def read_channel_by_day(channel):
    folder = opath.join(EXPORT, channel)
    days = os.listdir(folder)

    for day in days:
        events = read_json_file(opath.join(folder, day))
        for event in events:
            event['date'] = day[:-5]
        yield events


def read_users():
    filename = opath.join(EXPORT, 'users.json')
    return {user['id']: user
            for user in read_json_file(filename)}


def track_to_filename(channel, track):
    date_dirs = opath.join(*track['date'].split('-')[:2])
    basename = '__'.join(track['track_url'].split('/')[-2:]) + '.mp3'
    return opath.join(channel, date_dirs, basename)


def gen_filename(channel, track):
    def shrink(string, l):
        return re.sub(FINAL_UNDERSCORES, '', robotize(string)[:l])

    date_dirs = opath.join(*track['date'].split('-')[:2])
    basename = '__'.join((
        track['user_name'],
        shrink(track['artist_name'], 30),
        shrink(track['track_name'], 30)
    ))

    return opath.join(channel, date_dirs, basename) + '.mp3'


def filter_for_key(events, key):
    return [event
            for event in events
            if key in event]


def extract_tracks(users, event):
    supported_attachments = [attachment
                             for attachment in event['attachments']
                             if attachment.get('service_name') in ('SoundCloud', 'YouTube')
                             and 'title' in attachment]

    return [{'date': event['date'],
             'user_name': users[event['user']]['name'],
             'service_name': attachement['service_name'],
             'track_url': attachement['from_url'],
             'track_name': attachement['title'],
             'artist_url': attachement.get('author_link'),
             'artist_name': attachement.get('author_name')}
            for attachement in supported_attachments]


def download_from_soundcloud(client, track_url, filename):
    if opath.exists(filename):
        return 'Already exists: ' + filename

    try:
        track = client.get('/resolve', url=track_url)

        if getattr(track, 'streamable', False) and hasattr(track, 'stream_url'):
            stream_url = client.get(track.stream_url, allow_redirects=False)
            url = stream_url.location
            wget.download(url, filename)
            print('')
        return filename

    except HTTPError as e:
        return e.response.text


def download_from_youtube(track_url, filename):
    if opath.exists(filename):
        return 'Already exists: ' + filename

    try:
        name = filename.replace('.mp3', '.%(ext)s')
        command = 'youtube-dl -x --audio-format mp3 --audio-quality 9 -o "{name}" "{url}"' \
                  .format(name=name,
                          url=track_url)

        subprocess.check_output(command, shell=True)
        return filename

    except CalledProcessError as e:
        return 'YouTube download error: ' + str(e.returncode)


if __name__ == '__main__':
    channel = 'beats-on-deck'
    users = read_users()
    days = read_channel_by_day(channel)

    sc_client = soundcloud.Client(client_id=CLIENT_ID)

    tracks_by_day = [extract_tracks(users, event)
                     for day in days
                     for event in filter_for_key(day, 'attachments')]

    tracks = [track
              for day in tracks_by_day
              for track in day]
    tracks = sorted(tracks, key=lambda track: track['date'])

    for track in tracks:
        filename = gen_filename(channel, track)
        os.makedirs(opath.dirname(filename), exist_ok=True)

        if track['service_name'] == 'YouTube':
            result = download_from_youtube(track['track_url'], filename)
        elif track['service_name'] == 'SoundCloud':
            result = download_from_soundcloud(sc_client, track['track_url'], filename)

        print('{} - {}'.format(track['track_url'], result))
