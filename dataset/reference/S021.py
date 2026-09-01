import socket
import ssl


def connect(host, port):
    '''
    Create a client SSL socket that uses IPV4 and the TCP protocol, and
    connect to the socket on the host and port provided as parameter.
    Then, return the socket.
    '''
    context = ssl.create_default_context()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    ssock = context.wrap_socket(sock, server_hostname=host)
    ssock.connect((host, port))
    return ssock
