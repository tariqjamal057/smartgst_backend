from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.backends import default_backend
import base64
import sys


def read_pem_private_key(private_key_path: str):
    with open(private_key_path, "rb") as f:
        pem_data = f.read()

    try:
        private_key = serialization.load_pem_private_key(
            pem_data,
            password=b"Taxmate@123",
            backend=default_backend(),
        )
    except (TypeError, ValueError):
        private_key = serialization.load_pem_private_key(
            pem_data,
            password=None,
            backend=default_backend(),
        )
    return private_key


def sign(message: str, private_key_path: str) -> str:
    private_key = read_pem_private_key(private_key_path)
    signature = private_key.sign(
        message.encode("utf-8"),
        asym_padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def main():
    if len(sys.argv) < 3:
        print("Error: Missing arguments.", file=sys.stderr)
        print("Usage: python vayana_signer.py <message> <private_key_path>", file=sys.stderr)
        sys.exit(1)

    message = sys.argv[1]
    private_key_path = sys.argv[2]

    try:
        signature = sign(message, private_key_path)
        print(signature, end="")
    except Exception as e:
        print(f"Execution Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
