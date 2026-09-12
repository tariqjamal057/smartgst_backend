"""Subprocess bridge to the Vanaya (GSTN GSP) Java helpers.

The GSTN/Vayana crypto primitives are implemented, tested, and known-working
in Java under ``vanaya_api/`` (``GstOtpEncryptor``, ``GstDataDecryptor``,
``VayanaSignerApp``). Rather than porting them, we invoke those compiled
classes as CLI scripts -- the Java sources are compiled into ``.class`` files
on first use, so this stays dependency-light and self-provisioning.

Python only handles the parts that have no Java counterpart (plain base64
payloads from profile/search endpoints).
"""

import base64
import json
import subprocess
from pathlib import Path

JAVA_SOURCES = {
    "GstOtpEncryptor": "GstOtpEncryptor.java",
    "GstDataDecryptor": "GstDataDecryptor.java",
    "VayanaSignerApp": "VayanaSignerApp.java",
}


class VanayaCryptoError(Exception):
    """Raised when a Vanaya Java CLI helper fails."""


def resolve_source_dir(source_dir: str | Path | None) -> Path:
    """Return the directory holding the Java sources."""
    if source_dir is None:
        raise VanayaCryptoError("VANAYA_JAVA_SOURCE_DIR is not configured.")
    source = Path(source_dir)
    missing = [name for name in JAVA_SOURCES.values() if not (source / name).exists()]
    if missing:
        raise VanayaCryptoError(f"Missing Java sources in {source}: {', '.join(missing)}")
    return source


def compile_java(source_dir, class_dir: str | Path | None = None) -> Path:
    """Compile the Vanaya Java helpers, returning the class directory."""
    source = resolve_source_dir(source_dir)
    out = Path(class_dir) if class_dir else source
    out.mkdir(parents=True, exist_ok=True)

    # Only build classes that are missing or older than their sources.
    needs_build = False
    for class_name, source_name in JAVA_SOURCES.items():
        class_file = out / f"{class_name}.class"
        source_file = source / source_name
        if (not class_file.exists()) or (source_file.stat().st_mtime > class_file.stat().st_mtime):
            needs_build = True
            break

    if needs_build:
        sources = [str(source / name) for name in JAVA_SOURCES.values()]
        try:
            result = subprocess.run(
                ["javac", "-d", str(out), *sources],
                capture_output=True,
                text=True,
            )
        except FileNotFoundError as exc:
            raise VanayaCryptoError(
                "JDK (javac) is required to build the Vanaya Java helpers."
            ) from exc
        if result.returncode != 0:
            raise VanayaCryptoError(f"javac failed: {result.stderr}")
    return out


def _run_java(class_dir: Path, class_name: str, *args: str) -> str:
    """Run one Vanaya Java CLI helper and return its trimmed stdout."""
    if not (class_dir / f"{class_name}.class").exists():
        raise VanayaCryptoError(f"{class_name}.class not found in {class_dir}. Compile it first.")
    try:
        result = subprocess.run(
            ["java", "-cp", str(class_dir), class_name, *args],
            capture_output=True,
            text=True,
            timeout=120,
        )
    except FileNotFoundError as exc:
        raise VanayaCryptoError("JRE (java) is required to run Vanaya helpers.") from exc
    if result.returncode != 0:
        raise VanayaCryptoError(f"java {class_name} failed: {result.stderr.strip()}")
    return result.stdout.strip()


# --------------------------------------------------------------------------- #
# Public helper API (mirrors the previous pure-Python signatures)             #
# --------------------------------------------------------------------------- #
def ensure_built(source_dir, class_dir=None) -> Path:
    """Compile (if needed) and return the Java class directory."""
    return compile_java(source_dir, class_dir)


def sign_sha256(
    private_key_path: str,
    message: str,
    class_dir: Path,
    password: str = "",
) -> str:
    """SHA256withRSA signing via ``VayanaSignerApp`` (optional password)."""
    return _run_java(class_dir, "VayanaSignerApp", message, private_key_path, password)


def rsa_encrypt_app_key(public_key_path: str, app_key: str, class_dir: Path) -> str:
    """RSA-encrypt the raw ``app_key`` with the GSTN public key."""
    return _run_java(
        class_dir,
        "GstOtpEncryptor",
        "OTPREQUEST",
        "app-key",
        public_key_path,
        app_key,
        "app_key",
    )


def encrypt_otp(
    public_key_path: str,
    app_key: str,
    otp: str,
    class_dir: Path,
    username: str = "",
) -> str:
    """AES/ECB-encrypt ``otp`` with the raw app key via the Java helper."""
    return _run_java(
        class_dir,
        "GstOtpEncryptor",
        "AUTHTOKEN",
        username,
        public_key_path,
        app_key,
        "otp",
        otp,
    )


def decrypt_sek(app_key: str, encrypted_sek: str, class_dir: Path) -> str:
    """Decrypt the auth-response ``sek`` -> base64 EK."""
    return _run_java(class_dir, "GstDataDecryptor", "sek", app_key, encrypted_sek)


def decrypt_api_response(
    decrypted_sek: str,
    rek: str,
    data: str,
    class_dir: Path,
) -> str:
    """Two-step GSTN payload decryption -> plain JSON string."""
    return _run_java(class_dir, "GstDataDecryptor", "api_response", decrypted_sek, rek, data)


def decrypt_search_data(data: str) -> dict | str:
    """Decode the plain base64 JSON returned by profile/search endpoints."""
    decoded = base64.b64decode(data).decode("utf-8")
    try:
        return json.loads(decoded)
    except ValueError:
        return decoded
