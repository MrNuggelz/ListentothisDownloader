import argparse
import html
import json
import os
import re
import subprocess

from urllib.error import HTTPError

import eyed3
import youtube_dl
import urllib
from urllib.request import urlopen
from collections import namedtuple

from eyed3.id3 import Tag, ID3_V1, ID3_DEFAULT_VERSION
from youtube_dl.utils import DownloadError

Track = namedtuple('Track', ['url', 'artist', 'title', 'genre', 'year', 'month'])
comment_url = 'https://www.reddit.com/user/l2tbot/comments.json?limit=1000'
header = {"User-Agent": "l2tbotpy"}
track_regex = re.compile(
    r'<tr>\n<td align=\"left\"><a href=\"(?P<url>.+?)\">(?P<artist>.+?) (?:--|-) (?P<title>[^\[]+?)(?: ?\[(?P<genre>.*?[a-zA-Z]+?.*?)\]| ?[\(|\[](?P<year>[0-9 ]+)[\)|\]])+')

ydl = youtube_dl.YoutubeDL({
    'noplaylist': True,
    # 'ignoreerrors': True,
    'geo_bypass': True,
    # 'simulate': True,
    # 'verbose': True,
    'quiet': True,
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
        genre = "\x00".join([genre.strip() for genre in re.split(',|/',info['genre'])])
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
            if args.unify_genres:
                with open('genres', encoding='utf8') as f:
                    genre_list = [l.strip() for l in f.readlines()]
                data = unify_genres_in_tracks(song_list, genre_list)
            data.update({month: song_list})
            save_cache(data)
        return data
    data = get_song_list_from_reddit(month)
    if args.unify_genres:
        with open('genres', encoding='utf8') as f:
            genre_list = [l.strip() for l in f.readlines()]
        data = unify_genres_in_tracks(data,genre_list)
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
    months = [get_tracks_for_month(month) for month in submissions]
    if args.unify_genres:
        with open('genres', encoding='utf8') as f:
            genre_list = [l.strip() for l in f.readlines()]
        months = [(month,unify_genres_in_tracks(tracks,genre_list)) for month, tracks in months]
    return dict(months)


def unify_genres_in_tracks(tracks,genre_list):
    def check_genre(s1: str, s2: str):
        if s1[0].upper() != s2[0].upper():
            return False
        s1 = s1.upper().replace(' ', '').replace('-', '')
        s2 = s2.upper().replace(' ', '').replace('-', '')
        return s1 == s2

    def unify_genre(track):
        changed = False
        genres = track.genre.split('\x00')
        ugenres = []
        for genre in genres:
            if genre not in genre_list:
                la = list(filter(lambda s: check_genre(s, genre), genre_list))
                if len(la) > 0:
                    changed = True
                    print('changing', genre, 'to', la[0])
                    genre = la[0]
            ugenres.append(genre)
        if changed:
            track = track._replace(genre='\x00'.join(ugenres))
        return track

    return [unify_genre(track) for track in tracks]


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
    return os.path.exists(get_path(track))


def get_path(track):
    month = track.month
    if track is None:
        return ""
    filename = track.artist + ' - ' + track.title + '.mp3'
    filename = filename.replace('/', '').replace('?', '').replace('\"', '\'').replace(':', ';').replace('*', '')
    return 'songs/' + month + '/' + filename


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
        cmd = ['ffmpeg','-v','0','-y','-i','file:temp','-vn','-acodec','libmp3lame','-b:a','192k','file:temp.mp3']
        if args.verbose:
            print(' finished download')
        subprocess.run(cmd)
        if args.verbose:
            print(' finished conversion')
        filepath = 'songs/{0!s}/{1!s}.mp3'.format(track.month, filename)
        os.rename('temp.mp3', filepath)
        if not args.ignore_tags:
            set_tags(track)
        if args.verbose:
            print('finished:', filename)
        return True
    except (DownloadError, KeyError, HTTPError):
        return False


def set_tags(track):
    if args.verbose:
        print(' tagging', str(track.artist + ' - ' + track.title))
    album = 'Best of {0!s} 20{1!s} on /r/listentothis'.format(track.month[:-2], track.month[-2:])
    path = get_path(track)
    if path is None:
        return
    tag = Tag()
    tag.title = track.title
    tag.artist = track.artist
    tag.album_artist = "Various Artists"
    if track.year is not None:
        tag.year = track.year
    tag.album = album
    tag.genre = track.genre
    tag.save(filename=path, version=ID3_V1)
    tag.save(filename=path, version=ID3_DEFAULT_VERSION)
    if args.verbose:
        print(' finished tagging')


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
    eyed3.log.setLevel("ERROR")
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--month')
    parser.add_argument('-c', '--check', action='store_true')
    parser.add_argument('-cm', '--check-missing', action='store_true')
    parser.add_argument('-ct', '--check-tags', action='store_true')
    parser.add_argument('-it', '--ignore-tags', action='store_true')
    parser.add_argument('-v', '--verbose', action='store_true')
    parser.add_argument('-r', '--reload-songs', action='store_true')
    parser.add_argument('-dc', '--disable-cache', action='store_true')
    parser.add_argument('-uc', '--update-cache', action='store_true')
    parser.add_argument('-ug', '--unify-genres', action='store_true')
    args = parser.parse_args()

    if args.update_cache:
        if args.month is None:
            save_cache(get_all_song_lists_from_reddit())
        else:
            get_song_list(args.month)
    elif args.check or args.check_missing or args.check_tags:
        if args.check or args.check_missing:
            if args.month is None:
                dirs = [d for d in os.listdir("songs/") if os.path.isdir("songs/" + d)]
                for d in dirs:
                    check_missing_in_dir(d)
            else:
                check_missing_in_dir(args.month)
        if args.check or args.check_tags:
            if args.month is None:
                dirs = [d for d in os.listdir("songs/") if os.path.isdir("songs/" + d)]
                for d in dirs:
                    for song in get_song_list(d):
                        if song_exists(song):
                            set_tags(song)
            else:
                for song in get_song_list(args.month):
                    if song_exists(song):
                        set_tags(song)
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
