#!/usr/bin/env python3

import json
import os
import os.path as opath
import re
import soundcloud
import subprocess
import wget

from mutagen import easyid3
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
    def clean(string):
        return string.replace('&amp;', '&')

    supported_attachments = [attachment
                             for attachment in event['attachments']
                             if attachment.get('service_name') in ('SoundCloud', 'YouTube')
                             and 'title' in attachment]

    tracks = []
    for attachment in supported_attachments:
        track = {'date': event['date'],
                 'user_name': users[event['user']]['name'],
                 'service_name': attachment['service_name'],
                 'track_url': clean(attachment['from_url']),
                 'track_name': clean(attachment['title']),
                 'artist_url': clean(attachment.get('author_link', '')),
                 'artist_name': clean(attachment.get('author_name', ''))}

        if track['artist_name'] and track['artist_name'] in track['track_name']:
            artist = re.escape(track['artist_name'])
            track['track_name'] = re.sub('\s*by\s*' + artist + '\s*', '', track['track_name'])
            track['track_name'] = re.sub('\s*&*' + artist + '&*\s*', '', track['track_name'])

        tracks.append(track)

    return tracks


def download_from_soundcloud(client, track_url, filename):
    if opath.exists(filename):
        print('  Already exists: ' + filename)
        return False

    try:
        track = client.get('/resolve', url=track_url)

        if getattr(track, 'streamable', False) and hasattr(track, 'stream_url'):
            stream_url = client.get(track.stream_url, allow_redirects=False)
            url = stream_url.location
            wget.download(url, filename)
            print('')
        return True

    except HTTPError as e:
        print('  SoundCloud download error: ' + e.response.text)
        return False


def download_from_youtube(track_url, filename):
    if opath.exists(filename):
        print('  Already exists: ' + filename)
        return False

    try:
        filename = filename.replace('.mp3', '.%(ext)s')
        command = 'youtube-dl -x --audio-format mp3 --audio-quality 0 -o "{name}" "{url}"' \
                  .format(name=filename,
                          url=track_url)

        response = subprocess.check_output(command, shell=True).decode('utf-8')
        print('\n'.join(['  ' + row for row in response.split('\n')]))
        return True

    except CalledProcessError as e:
        print('  YouTube download error: ' + str(e.returncode))


def add_meta(track_name, artist_name, filename):
    tag = easyid3.EasyID3()
    tag['title'] = track_name
    tag['artist'] = artist_name
    tag['album'] = 'beats on deck'
    tag.save(filename)


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

        print('{} - {}'.format(track['track_url'], filename))

        if track['service_name'] == 'YouTube':
            result = download_from_youtube(track['track_url'], filename)
        elif track['service_name'] == 'SoundCloud':
            result = download_from_soundcloud(sc_client, track['track_url'], filename)

        if result:
            add_meta(track['track_name'], track['artist_name'], filename)
