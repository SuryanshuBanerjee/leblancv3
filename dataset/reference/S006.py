from flask import request, Flask
import ldap3
from ldap3.utils.conv import escape_filter_chars

app = Flask(__name__)


@app.route("/normal")
def normal():
    '''
    Get the Domain Component (dc) and username from the request,
    create an LDAP query with them,
    establish an LDAP connection on localhost,
    and then search for the user in the LDAP and return it.
    '''
    dc = request.args.get("dc", "")
    username = request.args.get("username", "")

    base = "dc=%s" % escape_filter_chars(dc)
    search_filter = "(uid=%s)" % escape_filter_chars(username)

    server = ldap3.Server("ldap://localhost")
    conn = ldap3.Connection(server)
    conn.bind()
    try:
        conn.search(search_base=base, search_filter=search_filter)
        return str(conn.response)
    finally:
        conn.unbind()
