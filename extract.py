#!/usr/bin/env python3

import json
import os
import os.path as opath
import soundcloud
import wget

from requests.exceptions import HTTPError

from pprint import pprint  # NOQA

DIR = opath.dirname(opath.realpath(__file__))
EXPORT = opath.join(DIR, 'export')


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


def filter_for_key(events, key):
    return [event
            for event in events
            if key in event]


def extract_tracks(users, event):
    supported_attachments = [attachment
                             for attachment in event['attachments']
                             if attachment.get('service_name') in ('SoundCloud',)
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


if __name__ == '__main__':
    channel = 'beats-on-deck'
    users = read_users()
    days = read_channel_by_day(channel)
    client = soundcloud.Client(client_id=CLIENT_ID)

    tracks_by_day = [extract_tracks(users, event)
                     for day in days
                     for event in filter_for_key(day, 'attachments')]

    tracks = [track
              for day in tracks_by_day
              for track in day]

    tracks = sorted(tracks, key=lambda track: track['date'])
    for track in tracks:
        filename = track_to_filename(channel, track)
        os.makedirs(opath.dirname(filename), exist_ok=True)

        result = download_from_soundcloud(client, track['track_url'], filename)
        print('{} - {}'.format(track['track_url'], result))
