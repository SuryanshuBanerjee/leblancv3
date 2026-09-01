from flask import request, Flask
import ldap
import ldap.dn
import ldap.filter

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

    base = "dc=%s" % ldap.dn.escape_dn_chars(dc)
    search_filter = ldap.filter.filter_format("(uid=%s)", [username])

    conn = ldap.initialize("ldap://localhost")
    try:
        conn.simple_bind_s()
        result = conn.search_s(base, ldap.SCOPE_SUBTREE, search_filter)
        return str(result)
    finally:
        conn.unbind_s()
