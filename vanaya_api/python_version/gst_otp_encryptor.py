from cryptography.hazmat.primitives import hashes, padding, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import sys


FIXED_OTP = "575757"


def read_pem_public_key(pem_path: str):
    with open(pem_path, "rb") as f:
        return serialization.load_pem_public_key(f.read(), backend=default_backend())


def decrypt_sek(encrypted_sek_b64: str, raw_app_key: str) -> str:
    key_bytes = raw_app_key.encode("utf-8")
    cipher = Cipher(algorithms.AES(key_bytes), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    unpadder = padding.PKCS7(128).unpadder()
    encrypted_bytes = base64.b64decode(encrypted_sek_b64)
    padded = decryptor.update(encrypted_bytes) + decryptor.finalize()
    decrypted = unpadder.update(padded) + unpadder.finalize()
    return base64.b64encode(decrypted).decode("utf-8")


def encrypt_app_key_rsa(public_key, raw_app_key: str) -> str:
    encrypted = public_key.encrypt(
        raw_app_key.encode("utf-8"),
        asym_padding.PKCS1v15(),
    )
    return base64.b64encode(encrypted).decode("utf-8")


def encrypt_otp_aes(raw_app_key: str) -> str:
    key_bytes = raw_app_key.encode("utf-8")
    cipher = Cipher(algorithms.AES(key_bytes), modes.ECB(), backend=default_backend())
    encryptor = cipher.encryptor()
    padder = padding.PKCS7(128).padder()
    padded_data = padder.update(FIXED_OTP.encode("utf-8")) + padder.finalize()
    encrypted = encryptor.update(padded_data) + encryptor.finalize()
    return base64.b64encode(encrypted).decode("utf-8")


def main():
    if len(sys.argv) == 4 and sys.argv[1].lower() == "decrypt_sek":
        raw_app_key = sys.argv[2]
        encrypted_sek = sys.argv[3]
        try:
            result = decrypt_sek(encrypted_sek, raw_app_key)
            print(result, end="")
        except Exception as e:
            print(f"Decryption Error: {e}", file=sys.stderr)
            sys.exit(1)
        return

    if len(sys.argv) < 5:
        print("Error: Missing arguments.", file=sys.stderr)
        print("Usage: python gst_otp_encryptor.py <action> <username> <gst_public_key_path> <raw_app_key> <output_type>", file=sys.stderr)
        sys.exit(1)

    action = sys.argv[1]
    user_name = sys.argv[2]
    public_key_path = sys.argv[3]
    raw_app_key_string = sys.argv[4]
    output_type = sys.argv[5]

    try:
        public_key = read_pem_public_key(public_key_path)
        encrypted_app_key = encrypt_app_key_rsa(public_key, raw_app_key_string)
        encrypted_otp = encrypt_otp_aes(raw_app_key_string)

        if output_type.lower() == "app_key":
            print(encrypted_app_key, end="")
        elif output_type.lower() == "otp":
            print(encrypted_otp, end="")
        else:
            payload = f'{{"action":"{action}","username":"{user_name}","app_key":"{encrypted_app_key}","otp":"{encrypted_otp}"}}'
            print(payload, end="")

    except Exception as e:
        print(f"Encryption Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
