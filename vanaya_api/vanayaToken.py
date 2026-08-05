import base64
import json
import os
import secrets
import sys
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "python_version"))

from gst_data_decryptor import decrypt_aes_ecb  # noqa: E402
from gst_otp_encryptor import (  # noqa: E402
    decrypt_sek,
    encrypt_app_key_rsa,
    encrypt_otp_aes,
    read_pem_public_key,
)
from vayana_signer import sign as vayana_sign  # noqa: E402

FIXED_OTP = "575757"


# ==========================================
# 1. PYTHON CRYPTOGRAPHY WRAPPERS
# ==========================================


def python_otp_encryptor(
    action: str, username: str, pem_path: str, raw_key: str, output_type: str
) -> str:
    public_key = read_pem_public_key(pem_path)
    encrypted_app_key = encrypt_app_key_rsa(public_key, raw_key)

    if output_type.lower() == "app_key":
        return encrypted_app_key
    elif output_type.lower() == "otp":
        return encrypt_otp_aes(raw_key)
    else:
        encrypted_otp = encrypt_otp_aes(raw_key)
        return json.dumps(
            {
                "action": action,
                "username": username,
                "app_key": encrypted_app_key,
                "otp": encrypted_otp,
            }
        )


def python_standalone_decryptor(
    mode: str, key_string: str, encrypted_payload: str, *extra_args
) -> str:
    if mode == "sek":
        return decrypt_sek(encrypted_payload, key_string)

    elif mode == "api_response":
        rek_encrypted = encrypted_payload
        data_encrypted = extra_args[0] if extra_args else ""

        ek_bytes = base64.b64decode(key_string)
        data_key_bytes = decrypt_aes_ecb(ek_bytes, rek_encrypted)
        decrypted_bytes = decrypt_aes_ecb(data_key_bytes, data_encrypted)
        return base64.b64decode(decrypted_bytes).decode("utf-8")

    raise ValueError(f"Invalid mode: {mode}")


def python_vayana_sign(
    cust_id: str, client_id: str, txn_id: str, gstin: str, api_action: str, private_key_path: str
) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S") + "+0530"
    auth_token_string = f"v2.0:{cust_id}:{client_id}:{txn_id}:{timestamp}:{gstin}:{api_action}"
    auth_signature = vayana_sign(auth_token_string, private_key_path)

    return {
        "X-Asp-Auth-Token": auth_token_string,
        "X-Asp-Auth-Signature": auth_signature,
    }


# ==========================================
# 2. VAYANA SIGNATURE & HEADERS LOGIC
# ==========================================


def generate_random_txn_id(prefix="TXN") -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = secrets.token_hex(2).upper()
    return f"{prefix}{timestamp}{random_suffix}"


# ==========================================
# 3. MAIN RUNTIME UTILITY WORKFLOW
# ==========================================

if __name__ == "__main__":
    vayana_private_key_path = r"C:\Users\Admin\vanaya key pair\taxmate.p8.pem"
    gst_public_pem_path = (
        r"C:\Users\Admin\Downloads\GST_Sandbox_Latest_Public_key\GST_Sandbox_Latest_Public_keys"
        r"\GSTN_G2B_SANDBOX_UAT_public.pem"
    )

    print("====================================================")
    print(" GST & VAYANA SYSTEM ORCHESTRATION GATEWAY")
    print("====================================================\n")

    print("Select workflow action:")
    print("[1] Generate Auth Token, Payload Credentials & OTP (Simultaneous Flow)")
    print("[2] Create GST Auth Token and Signature for Custom Action Type Only")
    print("[3] Decrypt Auth Response directly using raw JSON payload object string")
    print("[4] Decrypt Auth Response directly using Manual Field Inputs (auth_token, sek, expiry)")
    print("[5] Decrypt Core Transactional Response Data (e.g., GSTIN Search, Return Profile APIs)")

    workflow_choice = input("\nEnter choice option (1, 2, 3, 4, or 5): ").strip()

    user_gstin = "33CGFPA6633Q4Z4"
    username = "TN_NT2.21614"

    try:
        shared_raw_app_key = secrets.token_hex(16)

        if workflow_choice == "1":
            user_gstin = input(f"Enter GSTIN (Default: {user_gstin}): ").strip() or user_gstin
            username = input(f"Enter GST Username (Default: {username}): ").strip() or username

            print("\nProcessing synchronous structures for both OTPREQUEST and AUTHTOKEN...")

            txn_id_otp = generate_random_txn_id()
            vayana_headers_otp = python_vayana_sign(
                "taxmatetest", "", txn_id_otp, user_gstin, "OTPREQUEST", vayana_private_key_path
            )
            encrypted_app_key_otp = python_otp_encryptor(
                "OTPREQUEST", username, gst_public_pem_path, shared_raw_app_key, "app_key"
            )
            gst_payload_otp = {
                "action": "OTPREQUEST",
                "username": username,
                "app_key": encrypted_app_key_otp,
            }

            txn_id_auth = generate_random_txn_id()
            vayana_headers_auth = python_vayana_sign(
                "taxmatetest", "", txn_id_auth, user_gstin, "AUTHTOKEN", vayana_private_key_path
            )
            raw_json_string = python_otp_encryptor(
                "AUTHTOKEN", username, gst_public_pem_path, shared_raw_app_key, "payload"
            )
            gst_payload_auth = json.loads(raw_json_string)

            print("\n" + "#" * 60 + "\n 🔥 PHASE 1: OTPREQUEST DATA\n" + "#" * 60)
            print(f"X-Asp-Auth-Token:\n{vayana_headers_otp['X-Asp-Auth-Token']}\n")
            print(f"X-Asp-Auth-Signature:\n{vayana_headers_otp['X-Asp-Auth-Signature']}\n")
            print(f"GST Payload:\n{json.dumps(gst_payload_otp, indent=2)}")

            print("\n" + "#" * 60 + "\n 🚀 PHASE 2: AUTHTOKEN DATA (Shared App Key)\n" + "#" * 60)
            print(f"X-Asp-Auth-Token:\n{vayana_headers_auth['X-Asp-Auth-Token']}\n")
            print(f"X-Asp-Auth-Signature:\n{vayana_headers_auth['X-Asp-Auth-Signature']}\n")
            print(f"GST Payload:\n{json.dumps(gst_payload_auth, indent=2)}\n" + "#" * 60)

            print(f"\nTracking Session raw app_key string: {shared_raw_app_key}")

        elif workflow_choice == "2":
            user_gstin = input(f"Enter GSTIN (Default: {user_gstin}): ").strip() or user_gstin
            custom_action = (
                input("Enter Custom Action Type (e.g., RETTRACK, REQSTATUS): ").strip().upper()
            )
            if not custom_action:
                raise ValueError("Action type field parameter cannot remain empty.")

            print(f"\nGenerating tokens strictly optimized for: {custom_action}...")
            custom_txn_id = generate_random_txn_id()

            custom_vayana_headers = python_vayana_sign(
                cust_id="taxmatetest",
                client_id="",
                txn_id=custom_txn_id,
                gstin=user_gstin,
                api_action=custom_action,
                private_key_path=vayana_private_key_path,
            )

            print("\n" + "=" * 65)
            print(f" 🎯 CUSTOM VAYANA ISOLATED AUTH TOKENS FOR: {custom_action}")
            print("=" * 65)
            print(f"X-Asp-Auth-Token:\n{custom_vayana_headers['X-Asp-Auth-Token']}\n")
            print(f"X-Asp-Auth-Signature:\n{custom_vayana_headers['X-Asp-Auth-Signature']}")
            print("=" * 65)

        elif workflow_choice == "3":
            print(
                "\n"
                + "=" * 50
                + "\n 📥 STANDALONE AUTH DECRYPTION VIA FULL JSON OBJECT\n"
                + "=" * 50
            )
            input_app_key = input("Enter the unencrypted raw session app_key: ").strip()
            print(
                "\nPaste your complete GST authentication response JSON dictionary "
                "below and press Enter:"
            )
            raw_json_input = input().strip()

            parsed_json = json.loads(raw_json_input)
            target_sek = parsed_json.get("sek")
            target_token = parsed_json.get("auth_token")
            target_expiry = parsed_json.get("expiry")

            if not target_sek:
                raise ValueError("Could not extract 'sek' parameter element from JSON.")

            decrypted_sek = python_standalone_decryptor("sek", input_app_key, target_sek)

            print("\n" + "✅" * 20 + "\n 🎉 AUTH RESPONSE DECRYPTION SUCCESSFUL!\n" + "=" * 60)
            print(f"Auth Token Context:    {target_token}")
            print(f"Session Expiry Info:   {target_expiry} minutes")
            print(f"Decrypted Base64 SEK:  {decrypted_sek}")
            print("=" * 60)

        elif workflow_choice == "4":
            print(
                "\n"
                + "=" * 50
                + "\n 📥 STANDALONE AUTH DECRYPTION VIA INDIVIDUAL FIELDS\n"
                + "=" * 50
            )
            input_app_key = input("Enter the unencrypted raw session app_key: ").strip()
            received_auth_token = input("1. Enter auth_token value: ").strip()
            received_sek = input("2. Enter sek value: ").strip()
            received_expiry = input("3. Enter expiry configuration: ").strip()

            if not received_sek:
                raise ValueError("The SEK text block field cannot be left blank.")

            decrypted_sek = python_standalone_decryptor("sek", input_app_key, received_sek)

            print("\n" + "✅" * 20 + "\n 🎉 AUTH FIELD DECRYPTION SUCCESSFUL!\n" + "=" * 60)
            print(f"Your Auth Token:       {received_auth_token}")
            print(f"Session Expiry:        {received_expiry} minutes")
            print(f"Decrypted Base64 SEK:  {decrypted_sek}")
            print("=" * 60)

        elif workflow_choice == "5":
            print(
                "\n" + "=" * 50 + "\n 📥 GSTIN PROFILE & API DATA PAYLOAD DECRYPTION\n" + "=" * 50
            )
            input_decrypted_sek = input("Enter your already DECRYPTED Base64 SEK: ").strip()
            print("\nPaste the complete GST API response JSON (with rek, data fields):")
            encrypted_response_json = input().strip()

            if not input_decrypted_sek or not encrypted_response_json:
                raise ValueError(
                    "Both parameters (Decrypted SEK and Response JSON) are mandatory."
                )

            try:
                parsed = json.loads(encrypted_response_json)
                rek = parsed.get("rek", "")
                data = parsed.get("data", "")
                if not rek or not data:
                    raise ValueError("Response JSON must contain 'rek' and 'data' fields.")
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON input.")

            decrypted_json_data = python_standalone_decryptor(
                "api_response", input_decrypted_sek, rek, data
            )

            print(
                "\n" + "✅" * 20 + "\n 📦 DECRYPTED TRANSACTONAL DATA BLOCK ATTACHED:\n" + "=" * 60
            )
            try:
                print(json.dumps(json.loads(decrypted_json_data), indent=2))
            except Exception:
                print(decrypted_json_data)
            print("=" * 60)

        else:
            print("\n❌ Invalid choice selected. Please restart script and use options 1 to 5.")

    except Exception as e:
        print(f"\n🚨 Error executing framework orchestration: {e}")
