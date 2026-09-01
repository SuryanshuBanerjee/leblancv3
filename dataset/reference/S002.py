import mysql.connector


def get_connection():
    '''
    Return a connection to the database
    '''
    return mysql.connector.connect(host="localhost", user="", passwd="")


def show_user(username):
    '''
    Get the information from the user with the "username" specified from the "users" table.
    Return the user information.
    '''
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE username = %s", (username,))
        return cur.fetchall()
    finally:
        conn.close()
