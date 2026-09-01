"""Reference solution for S037 (CWE-020 — improper input validation / XML).
Secure: prefer defusedxml when available (blocks XXE / entity-expansion attacks);
fall back to stdlib ElementTree, which does not resolve external entities by
default. Returns the root Element, preserving the intended behaviour."""
try:
    from defusedxml.ElementTree import fromstring as _fromstring
except ImportError:  # defusedxml not installed; stdlib ET disables external entities
    from xml.etree.ElementTree import fromstring as _fromstring


def parse_xml(xml_string):
    """Parse xml_string and return the root element of the XML document."""
    return _fromstring(xml_string)
