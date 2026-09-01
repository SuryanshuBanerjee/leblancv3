import hashlib
import os

from flask import Flask, request
import MySQLdb

app = Flask(__name__)


# register url
@app.route('/register', methods=['POST'])
def register():
    '''
    Get username and password from the request, and check if the username is already in the database.
    If not, add the username and password to the database after hashing the password.
    '''
    username = request.form.get('username') or request.args.get('username', '')
    password = request.form.get('password') or request.args.get('password', '')
    if not username or not password:
        return "missing username or password", 400

    conn = MySQLdb.connect(host="localhost", user="", passwd="", db="app")
    try:
        cur = conn.cursor()
        cur.execute("SELECT username FROM users WHERE username = %s", (username,))
        if cur.fetchone() is not None:
            return "username already taken", 409

        salt = os.urandom(16).hex()
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
        ).hex()
        cur.execute(
            "INSERT INTO users (username, password) VALUES (%s, %s)",
            (username, salt + "$" + digest),
        )
        conn.commit()
        return "registered", 201
    finally:
        conn.close()
