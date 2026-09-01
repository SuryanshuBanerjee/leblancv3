"""Real RFC 4515 escaping — secure generated code depends on this behaving."""


def escape_filter_chars(assertion_value, escape_mode=0):
    s = str(assertion_value)
    s = s.replace("\\", "\\5c")
    s = s.replace("*", "\\2a")
    s = s.replace("(", "\\28")
    s = s.replace(")", "\\29")
    s = s.replace("\x00", "\\00")
    return s


def filter_format(filter_template, assertion_values):
    return filter_template % tuple(escape_filter_chars(v) for v in assertion_values)
