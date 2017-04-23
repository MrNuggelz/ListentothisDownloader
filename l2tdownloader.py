import argparse
import html
import json
import os
import re
import subprocess
import taglib

from urllib.error import HTTPError

import youtube_dl
import urllib
from urllib.request import urlopen
from collections import namedtuple

from youtube_dl.utils import ExtractorError, DownloadError

Track = namedtuple('Track', ['url', 'artist', 'title', 'genre', 'year', 'month'])
comment_url = 'https://www.reddit.com/user/l2tbot/comments.json?limit=1000'
header = {"User-Agent": "l2tbotpy"}
track_regex = re.compile(
    r'<tr>\n<td align=\"left\"><a href=\"(?P<url>.+?)\">(?P<artist>.+?) (?:--|-) (?P<title>.+?)(?: ?\[(?P<genre>.+?)\]| ?\((?P<year>\d+)\))+')

ydl = youtube_dl.YoutubeDL({
    'noplaylist': True,
    # 'ignoreerrors': True,
    'geo_bypass': True,
    # 'simulate': True,
    # 'verbose': True,
    'quiet': True,
    'outtmpl': '%(id)s.%(ext)s',
    'format': 'bestaudio/best',
    'postprocessors': [{
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '192'
    }]
})


def track_from_match(match: re.match, month: str) -> Track:
    info = match.groupdict()
    year = ''
    genre = []
    if 'year' in info:
        year = info['year']
    if 'genre' in info:
        genre = [genre.strip() for genre in re.split(',|/',info['genre'])]
    return Track(info['url'], info['artist'], info['title'],
                 genre, year, month)


def get_song_list_from_reddit(month):
    def get_tracks_html(submission):
        return [track_from_match(match, month) for match in
                track_regex.finditer(html.unescape(html.unescape(submission['body_html'])))]

    req = urllib.request.Request(comment_url, headers=header)
    resp = urllib.request.urlopen(req).read().decode('utf-8')

    submissions = [x['data'] for x in json.loads(resp)['data']['children'] if
                   x['data']['subreddit_name_prefixed'] == 'r/listentothis' and month[:-2] + ' 20' + month[-2:] in
                   x['data'][
                       'link_title']]
    result = [get_tracks_html(submission) for submission in submissions]
    if len(result) < 1:
        print(month + ' not found')
        return
    return result[0]


def get_song_list(month):
    if args.disable_cache:
        return get_song_list_from_reddit(month)
    if os.path.isfile("cache.dict"):
        cache = load_cache()
        data = {k: [Track(*track_info) for track_info in v] for k, v in cache.items()}
        if month in data and data[month] is not None:
            return data[month]
        song_list = get_song_list_from_reddit(month)
        if song_list is not None:
            data.update({month: song_list})
            save_cache(data)
        return data
    data = get_song_list_from_reddit(month)
    save_cache(dict({month: data}))
    return data


def get_all_song_lists_from_reddit():
    def get_tracks_for_month(submission):
        regex = re.compile(r'.*?Top 50 posts in r/listentothis for (.+?) \d\d(\d+)')
        m = regex.match(submission['link_title'])
        month = m.group(1) + m.group(2)
        return month, [track_from_match(match, month) for match in
                       track_regex.finditer(html.unescape(html.unescape(submission['body_html'])))]

    req = urllib.request.Request(comment_url, headers=header)
    resp = urllib.request.urlopen(req).read().decode('utf-8')

    submissions = [x['data'] for x in json.loads(resp)['data']['children'] if
                   x['data']['subreddit_name_prefixed'] == 'r/listentothis']
    return dict([get_tracks_for_month(month) for month in submissions])


def check_missing_in_dir(month):
    data = get_song_list(month)
    if data is None:
        return
    missing_songs = filter(lambda a: not song_exists(a), data)
    if args.verbose:
        print('Missing Songs for', month + ':')
    f = open('missingSongs' + month + '.txt', 'wb')
    for song in missing_songs:
        if args.verbose:
            print(" " + str(song.artist + ' - ' + song.title))
        text = str(song.artist + ' - ' + song.title) + '\n'
        f.write(text.encode('utf8'))
    f.close()


def song_exists(track):
    month = track.month
    if track is None:
        return False
    filename = track.artist + ' - ' + track.title + '.mp3'
    filename = filename.replace('/', '').replace('?', '').replace('\"','\'').replace(':',';').replace('*','')
    return os.path.exists('songs/' + month + '/' + filename)


def download(track):
    if track is None:
        return
    filename = '{0!s} - {1!s}'.format(track.artist, track.title)
    filename = filename.replace('/', '').replace('?', '').replace('\"','\'').replace(':',';').replace('*','')
    if not args.reload_songs and song_exists(track):
        if args.verbose:
            print('skipping existing:', filename)
        return True
    if args.verbose:
        print('loading:', filename, track.url)
    try:
        dwn_url = ydl.extract_info(track.url, download=False)['url']
        urllib.request.urlretrieve(dwn_url, 'temp')
        cmd = 'ffmpeg -v 0 -y -i file:temp -vn -acodec libmp3lame -b:a 192k file:temp.mp3'
        if args.verbose:
            print(' finished download')
        subprocess.run(cmd)
        if args.verbose:
            print(' finished conversion')
        album = 'Best of {0!s} 20{1!s} on /r/listentothis'.format(track.month[:-2], track.month[-2:])
        mp3 = taglib.File('temp.mp3')
        mp3.tags['ARTIST'] = [track.artist]
        mp3.tags['TITLE'] = [track.title]
        mp3.tags['ALBUM'] = [album]
        if track.year is not None:
            mp3.tags['DATE'] = [track.year]
        if track.genre is not None:
            mp3.tags['GENRE'] = track.genre
        mp3.save()
        mp3.close()
        os.rename('temp.mp3', 'songs/{0!s}/{1!s}.mp3'.format(track.month, filename))
        if args.verbose:
            print('finished:', filename)
        return True
    except (DownloadError, KeyError,HTTPError):
        return False


def download_month(month):
    data = get_song_list(month)
    if not os.path.exists("songs/" + month + "/"):
        os.makedirs("songs/" + month + "/")
    missing_songs = [track for track in data if not download(track)]
    if args.verbose:
        print("Missing Songs:")
    f = open('missingSongs' + month + '.txt', 'wb')
    for song in missing_songs:
        if args.verbose:
            print(" " + str(song.artist + ' - ' + song.title))
        text = str(song.artist + ' - ' + song.title) + '\n'
        f.write(text.encode('utf8'))
    f.close()


def load_cache():
    file = open("cache.dict", "r")
    data = json.load(file)
    file.close()
    return {k: [Track(**track) for track in tracks] for k, tracks in data.items()}


def save_cache(data):
    file = open("cache.dict", "w")
    json.dump({k: [track._asdict() for track in tracks] for k, tracks in data.items()}, file, indent=2)
    file.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--month')
    parser.add_argument('-c', '--check', action='store_true')
    parser.add_argument('-dc', '--disable-cache', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-r', '--reload-songs', action='store_true')
    parser.add_argument('--update-cache', action='store_true')
    args = parser.parse_args()

    if args.update_cache:
        if args.month is None:
            save_cache(get_all_song_lists_from_reddit())
        else:
            get_song_list(args.month)
    elif args.check:
        if args.month is None:
            dirs = [d for d in os.listdir("songs/") if os.path.isdir("songs/" + d)]
            for d in dirs:
                check_missing_in_dir(d)
        else:
            check_missing_in_dir(args.month)
    elif args.month is None:
        months = get_all_song_lists_from_reddit()
        save_cache(months)
        for monthh in months:
            download_month(monthh)
    else:
        download_month(args.month)
    if os.path.exists('temp'):
        os.remove('temp')
    if os.path.exists('temp.mp3'):
        os.remove('temp.mp3')
