# Slack Media Downloader

### Install

```shell
$ brew install ffmpeg
$ pip3 install -r requirements.txt
```

### Run

```shell
# CLIENT_ID is your SoundCloud client ID
# channel is the Slack channel to search for tracks
# export_path is the path to the unzipped Slack export

$ CLIENT_ID={} python extract.py --channel channel_name export_path
```
