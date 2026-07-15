from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import base64
import sys


def decrypt_aes_ecb(key_bytes: bytes, encrypted_b64: str) -> bytes:
    cipher = Cipher(algorithms.AES(key_bytes), modes.ECB(), backend=default_backend())
    decryptor = cipher.decryptor()
    unpadder = padding.PKCS7(128).unpadder()
    encrypted_bytes = base64.b64decode(encrypted_b64)
    padded = decryptor.update(encrypted_bytes) + decryptor.finalize()
    return unpadder.update(padded) + unpadder.finalize()


def main():
    if len(sys.argv) < 3:
        print("Error: Missing arguments.", file=sys.stderr)
        print("Usage: python gst_data_decryptor.py <mode> <encryption_key> <encrypted_data>", file=sys.stderr)
        print("       python gst_data_decryptor.py api_response <decrypted_sek(b64)> <rek> <data>", file=sys.stderr)
        print("Modes: 'sek' (decrypt SEK with raw app_key), 'api_response' (two-step GST decrypt)", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1].lower()
    key_string = sys.argv[2]
    encrypted_data = sys.argv[3]

    try:
        if mode == "sek":
            key_bytes = key_string.encode("utf-8")
            decrypted = decrypt_aes_ecb(key_bytes, encrypted_data)
            print(base64.b64encode(decrypted).decode("utf-8"), end="")

        elif mode == "api_response":
            if len(sys.argv) < 5:
                print("Error: api_response mode requires 4 args: mode decrypted_sek rek data", file=sys.stderr)
                sys.exit(1)

            rek_encrypted = encrypted_data
            data_encrypted = sys.argv[4]

            ek_bytes = base64.b64decode(key_string)

            # Step 1: decrypt rek with EK to get data_key
            data_key_bytes = decrypt_aes_ecb(ek_bytes, rek_encrypted)

            # Step 2: decrypt data with data_key
            decrypted_bytes = decrypt_aes_ecb(data_key_bytes, data_encrypted)

            # Final base64 decode step as done in Java
            result = base64.b64decode(decrypted_bytes).decode("utf-8")
            print(result, end="")

        else:
            print(f"Error: Invalid mode '{mode}'. Use 'sek' or 'api_response'.", file=sys.stderr)
            sys.exit(1)

    except Exception as e:
        print(f"Decryption Execution Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
