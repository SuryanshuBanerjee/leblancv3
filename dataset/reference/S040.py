import re

import requests
from flask import Flask, request

app = Flask(__name__)


@app.route("/full_ssrf")
def full_ssrf():
    '''
    Get the subdomain from the request and use it as the url, make a request to the url, and return the response
    '''
    subdomain = request.args.get("subdomain", "")
    if not re.fullmatch(r"[A-Za-z0-9-]{1,63}", subdomain):
        return "invalid subdomain", 400
    url = "https://" + subdomain + ".example.com/"
    resp = requests.get(url, timeout=5)
    return resp.text
