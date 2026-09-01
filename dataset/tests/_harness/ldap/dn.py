"""Minimal RFC 4514 DN escaping."""


def escape_dn_chars(s):
    s = str(s)
    for ch in ("\\", ",", "+", '"', "<", ">", ";", "="):
        s = s.replace(ch, "\\" + ch)
    if s.startswith("#") or s.startswith(" "):
        s = "\\" + s
    if s.endswith(" "):
        s = s[:-1] + "\\ "
    return s
