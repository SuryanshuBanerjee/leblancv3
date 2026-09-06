"""
Deliberately vulnerable Python — a fixture, not production code, not a mistake.

WHY THIS FILE EXISTS
--------------------
It is a known-bad input used to demonstrate and smoke-check Engine B end to end,
especially the MCP `scan_path` tool (which scans real files/directories on disk,
as opposed to `scan_code`, which takes an in-memory snippet). Point a scanner at
it and you should get a predictable spread of findings across several CWE
categories — if you get zero, the scanner wiring is broken, not the file.

    python -c "from backend.engine_b_scan import scan_path; print(scan_path('demo/vulnerable_example.py'))"

    # or, through the MCP server, from any MCP-speaking agent:
    #   scan_path("D:/LYPROJECT/v3/demo/vulnerable_example.py")

WHAT IS WRONG WITH IT, ON PURPOSE (expected findings)
-----------------------------------------------------
    CWE-798  hard-coded credential                (DB_PASSWORD below)
    CWE-89   SQL injection via f-string query     (get_user)
    CWE-78   OS command injection via os.system   (ping_host)
    CWE-95   eval() on caller-supplied input      (run_expression)
    CWE-502  pickle.loads on untrusted data       (load_session)
    CWE-328  weak hash (MD5) for passwords        (hash_password)
    CWE-22   path traversal via unvalidated join  (read_report)

NEVER import, call, or deploy anything in this file. It is scanner bait.
"""

import os
import sqlite3
import pickle
import hashlib

DB_PASSWORD = "hunter2"  # CWE-798: hard-coded credential


def get_user(username):
    conn = sqlite3.connect("users.db")
    cur = conn.cursor()
    query = f"SELECT * FROM users WHERE username = '{username}'"  # CWE-89
    cur.execute(query)
    return cur.fetchone()


def ping_host(host):
    os.system("ping -n 1 " + host)  # CWE-78


def run_expression(expr):
    return eval(expr)  # CWE-95


def load_session(blob):
    return pickle.loads(blob)  # CWE-502


def hash_password(password):
    return hashlib.md5(password.encode()).hexdigest()  # CWE-328


def read_report(filename):
    path = "reports/" + filename  # CWE-22
    with open(path) as f:
        return f.read()
