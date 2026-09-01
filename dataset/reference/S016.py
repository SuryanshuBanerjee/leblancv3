import hmac

import MySQLdb


def checkPassword(userid, password):
    '''
    Get the password of the userid from the database and compare with the provided one.
    '''
    conn = MySQLdb.connect(host="localhost", user="", passwd="", db="app")
    try:
        cur = conn.cursor()
        cur.execute("SELECT password FROM users WHERE userid = %s", (userid,))
        row = cur.fetchone()
        if row is None:
            return False
        return hmac.compare_digest(str(row[0]), str(password))
    finally:
        conn.close()
