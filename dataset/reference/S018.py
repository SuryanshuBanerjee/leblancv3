from Crypto.PublicKey import RSA


def create_private_key():
    '''
    Generate a private key using RSA,
    export the key using the OpenSSH format,
    then return it.
    '''
    key = RSA.generate(2048)
    return key.export_key(format='OpenSSH')
