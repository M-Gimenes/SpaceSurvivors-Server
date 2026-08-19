"""Chaves e assinaturas: chave de API por processo e assinatura RSA das respostas."""
import logging
import os

from cryptography.fernet import Fernet
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


class CryptoService():
    def __init__(self, key_master_path, private_key_path):
        with open(key_master_path, 'rb') as key_master:
            cryptograph = Fernet(key_master.read())

        # Chave de API gerada uma vez por processo e entregue já cifrada ao cliente.
        self.key = (os.urandom(64)).hex()
        self.encrypted_key = cryptograph.encrypt(self.key.encode()).decode()

        with open(private_key_path, 'rb') as key_file:
            self.private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,
                backend=default_backend()
            )

    def get_signature(self, data):
        try:
            return self.private_key.sign(
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH
                ),
                hashes.SHA256()
            )
        except Exception as e:
            logging.error(f"Error in get_signature: {e}")
            return None

    def get_public_key(self):
        try:
            return self.private_key.public_key().public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
        except Exception as e:
            logging.error(f"Error in get_public_key: {e}")
            return None
