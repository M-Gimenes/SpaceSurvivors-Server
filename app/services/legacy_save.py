"""Migração dos saves da versão 1.0.0.

A 1.0.0 guardava o save (um pickle) assinado pelo servidor com RSA. A 1.0.1 não usa
mais assinatura: o recorde fica no servidor. Esta classe existe só para que um jogador
antigo prove que o nick é dele (rota /claim), apresentando o save assinado que tem no PC.
"""
import io
import logging
import pickle

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

log = logging.getLogger('spacesurvivors')

# Um save da 1.0.0 tem poucas dezenas de bytes; o limite evita payloads gigantes.
MAX_SAVE_BYTES = 4096


class _NoGlobalsUnpickler(pickle.Unpickler):
    """Recusa qualquer classe ou função no pickle.

    O save só pode conter tipos básicos (dict, str, int). Sem isso, um pickle forjado
    executaria código no servidor ao ser carregado.
    """

    def find_class(self, module, name):
        raise pickle.UnpicklingError(f'global proibido no save: {module}.{name}')


class LegacySaves():
    def __init__(self, private_key_path):
        self.public_key = None
        try:
            with open(private_key_path, 'rb') as key_file:
                private_key = serialization.load_pem_private_key(key_file.read(), password=None)
            self.public_key = private_key.public_key()
        except FileNotFoundError:
            log.warning("private_key ausente: migração de saves da 1.0.0 (/claim) desativada")

    @property
    def enabled(self):
        return self.public_key is not None

    def read(self, save_bytes, signature):
        """Devolve o dict do save se a assinatura for válida; senão None.

        A assinatura é conferida ANTES de abrir o pickle.
        """
        if not self.enabled or not save_bytes or len(save_bytes) > MAX_SAVE_BYTES:
            return None
        try:
            self.public_key.verify(
                signature,
                save_bytes,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
        except InvalidSignature:
            return None
        try:
            content = _NoGlobalsUnpickler(io.BytesIO(save_bytes)).load()
        except Exception as e:
            log.warning(f"Save assinado mas ilegível em /claim: {e}")
            return None
        return content if isinstance(content, dict) else None
