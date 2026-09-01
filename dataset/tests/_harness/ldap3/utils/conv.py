"""Real RFC 4515 escaping — secure generated code depends on this behaving."""


def escape_filter_chars(text, encoding=None):
    s = str(text)
    s = s.replace("\\", "\\5c")
    s = s.replace("*", "\\2a")
    s = s.replace("(", "\\28")
    s = s.replace(")", "\\29")
    s = s.replace("\x00", "\\00")
    return s


def escape_bytes(b):
    return "".join("\\%02x" % x for x in bytes(b))
