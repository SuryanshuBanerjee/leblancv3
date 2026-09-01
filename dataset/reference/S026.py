import json
import urllib.request as request
from urllib.parse import urlparse


def readJSON(url):
    '''
    Read a json file from a url
    and return the parsed json object
    '''
    if urlparse(url).scheme not in ("http", "https"):
        raise ValueError("only http(s) URLs are allowed")
    with request.urlopen(url) as resp:
        return json.load(resp)
