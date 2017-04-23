# ListentothisDownloader

## Requirements

- [python3](https://www.python.org/)
- [youtube-dl](https://pypi.python.org/pypi/youtube_dl)
- [pytaglib](https://pypi.python.org/pypi/pytaglib)

## Usage

```
usage: l2tdownloader.py [-h] [-m MONTH] [-c] [-dc] [-v] [-r] [--update-cache]

optional arguments:
  -h, --help            	show this help message and exit
  -m MONTH, --month MONTH 	eg. September16
  -c, --check           	check missing songs
  -dc, --disable-cache  	don't cache the songlists
  -v, --verbose
  -r, --reload-songs    	force reload songs
  --update-cache        	updates the songlist (for usage)
```


If you don't define a month, all month will be loaded.