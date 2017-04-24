# ListentothisDownloader

This script was made for downloading the monthly TOP 50 lists from /r/listentothis posted and set the ID3 tags.

## Requirements

- [python3](https://www.python.org/)
- [youtube-dl](https://pypi.python.org/pypi/youtube_dl)
- [eyed3](https://pypi.python.org/pypi/eyeD3/0.8.0b1) for python3

## Usage

```
usage: l2tdownloader.py [-h] [-m MONTH] [-c] [-cm] [-ct] [-it] [-v] [-r] [-dc]
                        [-uc]

optional arguments:
  -h, --help                show this help message and exit
  -m MONTH, --month MONTH   eg. September16
  -c, --check               check missing songs and id3 tags
  -ct, --check-tags         check missing songs
  -it, --ignore-tags        checks id3 tags
  -v, --verbose
  -r, --reload-songs        force reload songs
  -dc, --disable-cache      don't cache the songlists
  -uc, --update-cache       updates the songlist
```


If you don't define a month, all month will be loaded.
