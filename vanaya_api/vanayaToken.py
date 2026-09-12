import json
import secrets
import subprocess
from datetime import datetime

# ==========================================
# 1. SUBPROCESS UTILITY INTERFACE MAPPINGS
# ==========================================


def call_java_otp_encryptor(
    action: str, username: str, pem_path: str, raw_key: str, output_type: str, java_dir: str
) -> str:
    """Calls GstOtpEncryptor.class to process asymmetric/symmetric authentications via Java."""
    try:
        process = subprocess.Popen(
            [
                "java",
                "-cp",
                java_dir,
                "GstOtpEncryptor",
                action,
                username,
                pem_path,
                raw_key,
                output_type,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"GstOtpEncryptor failed: {stderr}")
        return stdout.strip()
    except Exception as e:
        raise RuntimeError(f"Could not connect to GstOtpEncryptor wrapper: {e}")


def call_java_standalone_decryptor(
    mode: str, key_string: str, encrypted_payload: str, java_dir: str, *extra_args
) -> str:
    """Calls GstDataDecryptor.class to handle decryptions safely for SEKs or transactional API data packages."""
    try:
        cmd = ["java", "-cp", java_dir, "GstDataDecryptor", mode, key_string, encrypted_payload]
        if extra_args:
            cmd.extend(extra_args)
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"GstDataDecryptor operation failed: {stderr}")
        return stdout.strip()
    except Exception as e:
        raise RuntimeError(f"Could not connect to GstDataDecryptor runtime structure: {e}")


# ==========================================
# 2. VAYANA SIGNATURE & HEADERS LOGIC
# ==========================================


def generate_random_txn_id(prefix="TXN") -> str:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    random_suffix = secrets.token_hex(2).upper()
    return f"{prefix}{timestamp}{random_suffix}"


def generate_vayana_auth_headers_via_java(
    cust_id: str,
    client_id: str,
    txn_id: str,
    gstin: str,
    api_action: str,
    private_key_path: str,
    java_class_dir: str,
) -> dict:
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S") + "+0530"
    auth_token_string = f"v2.0:{cust_id}:{client_id}:{txn_id}:{timestamp}:{gstin}:{api_action}"

    try:
        process = subprocess.Popen(
            [
                "java",
                "-cp",
                java_class_dir,
                "VayanaSignerApp",
                auth_token_string,
                private_key_path,
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        stdout, stderr = process.communicate()
        if process.returncode != 0:
            raise RuntimeError(f"VayanaSignerApp processing failed: {stderr}")
        auth_signature_string = stdout.strip()
    except Exception as e:
        raise RuntimeError(f"Could not execute Java runtime framework: {e}")

    return {
        "X-Asp-Auth-Token": auth_token_string,
        "X-Asp-Auth-Signature": auth_signature_string,
    }


# ==========================================
# 3. MAIN RUNTIME UTILITY WORKFLOW
# ==========================================

if __name__ == "__main__":
    vayana_private_key_path = r"C:\Users\Admin\vanaya key pair\taxmate.p8.pem"
    java_folder_dir = r"C:\Users\Admin\OneDrive\Desktop"
    gst_public_pem_path = r"C:\Users\Admin\Downloads\GST_Sandbox_Latest_Public_key\GST_Sandbox_Latest_Public_keys\GSTN_G2B_SANDBOX_UAT_public.pem"

    print("====================================================")
    print(" GST & VAYANA SYSTEM ORCHESTRATION GATEWAY")
    print("====================================================\n")

    # Display Workflow Options
    print("Select workflow action:")
    print("[1] Generate Auth Token, Payload Credentials & OTP (Simultaneous Flow)")
    print("[2] Create GST Auth Token and Signature for Custom Action Type Only")
    print("[3] Decrypt Auth Response directly using raw JSON payload object string")
    print("[4] Decrypt Auth Response directly using Manual Field Inputs (auth_token, sek, expiry)")
    print("[5] Decrypt Core Transactional Response Data (e.g., GSTIN Search, Return Profile APIs)")

    workflow_choice = input("\nEnter choice option (1, 2, 3, 4, or 5): ").strip()

    # Fallbacks configured according to parameters
    user_gstin = "33CGFPA6633Q4Z4"
    username = "TN_NT2.21614"

    try:
        shared_raw_app_key = secrets.token_hex(16)

        # --------------------------------------------------
        # WORKFLOW OPTION 1: SIMULTANEOUS DUAL GENERATION
        # --------------------------------------------------
        if workflow_choice == "1":
            user_gstin = input(f"Enter GSTIN (Default: {user_gstin}): ").strip() or user_gstin
            username = input(f"Enter GST Username (Default: {username}): ").strip() or username

            print("\nProcessing synchronous structures for both OTPREQUEST and AUTHTOKEN...")

            txn_id_otp = generate_random_txn_id()
            vayana_headers_otp = generate_vayana_auth_headers_via_java(
                "taxmatetest",
                "",
                txn_id_otp,
                user_gstin,
                "OTPREQUEST",
                vayana_private_key_path,
                java_folder_dir,
            )
            encrypted_app_key_otp = call_java_otp_encryptor(
                "OTPREQUEST",
                username,
                gst_public_pem_path,
                shared_raw_app_key,
                "app_key",
                java_folder_dir,
            )
            gst_payload_otp = {
                "action": "OTPREQUEST",
                "username": username,
                "app_key": encrypted_app_key_otp,
            }

            txn_id_auth = generate_random_txn_id()
            vayana_headers_auth = generate_vayana_auth_headers_via_java(
                "taxmatetest",
                "",
                txn_id_auth,
                user_gstin,
                "AUTHTOKEN",
                vayana_private_key_path,
                java_folder_dir,
            )
            raw_json_string_from_java = call_java_otp_encryptor(
                "AUTHTOKEN",
                username,
                gst_public_pem_path,
                shared_raw_app_key,
                "payload",
                java_folder_dir,
            )
            gst_payload_auth = json.loads(raw_json_string_from_java)

            print("\n" + "#" * 60 + "\n 🔥 PHASE 1: OTPREQUEST DATA\n" + "#" * 60)
            print(f"X-Asp-Auth-Token:\n{vayana_headers_otp['X-Asp-Auth-Token']}\n")
            print(f"X-Asp-Auth-Signature:\n{vayana_headers_otp['X-Asp-Auth-Signature']}\n")
            print(f"GST Payload:\n{json.dumps(gst_payload_otp, indent=2)}")

            print("\n" + "#" * 60 + "\n 🚀 PHASE 2: AUTHTOKEN DATA (Shared App Key)\n" + "#" * 60)
            print(f"X-Asp-Auth-Token:\n{vayana_headers_auth['X-Asp-Auth-Token']}\n")
            print(f"X-Asp-Auth-Signature:\n{vayana_headers_auth['X-Asp-Auth-Signature']}\n")
            print(f"GST Payload:\n{json.dumps(gst_payload_auth, indent=2)}\n" + "#" * 60)

            print(f"\nTracking Session raw app_key string: {shared_raw_app_key}")

        # --------------------------------------------------
        # WORKFLOW OPTION 2: ISOLATED CUSTOM TARGET ACTION
        # --------------------------------------------------
        elif workflow_choice == "2":
            user_gstin = input(f"Enter GSTIN (Default: {user_gstin}): ").strip() or user_gstin
            custom_action = (
                input("Enter Custom Action Type (e.g., RETTRACK, REQSTATUS): ").strip().upper()
            )
            if not custom_action:
                raise ValueError("Action type field parameter cannot remain empty.")

            print(f"\nGenerating tokens strictly optimized for: {custom_action}...")
            custom_txn_id = generate_random_txn_id()

            custom_vayana_headers = generate_vayana_auth_headers_via_java(
                cust_id="taxmatetest",
                client_id="",
                txn_id=custom_txn_id,
                gstin=user_gstin,
                api_action=custom_action,
                private_key_path=vayana_private_key_path,
                java_class_dir=java_folder_dir,
            )

            print("\n" + "=" * 65)
            print(f" 🎯 CUSTOM VAYANA ISOLATED AUTH TOKENS FOR: {custom_action}")
            print("=" * 65)
            print(f"X-Asp-Auth-Token:\n{custom_vayana_headers['X-Asp-Auth-Token']}\n")
            print(f"X-Asp-Auth-Signature:\n{custom_vayana_headers['X-Asp-Auth-Signature']}")
            print("=" * 65)

        # --------------------------------------------------
        # WORKFLOW OPTION 3: RAW JSON OBJECT AUTH DECRYPTION
        # --------------------------------------------------
        elif workflow_choice == "3":
            print(
                "\n"
                + "=" * 50
                + "\n 📥 STANDALONE AUTH DECRYPTION VIA FULL JSON OBJECT\n"
                + "=" * 50
            )
            input_app_key = input("Enter the unencrypted raw session app_key: ").strip()
            print(
                "\nPaste your complete GST authentication response JSON dictionary below and press Enter:"
            )
            raw_json_input = input().strip()

            parsed_json = json.loads(raw_json_input)
            target_sek = parsed_json.get("sek")
            target_token = parsed_json.get("auth_token")
            target_expiry = parsed_json.get("expiry")

            if not target_sek:
                raise ValueError("Could not extract 'sek' parameter element from JSON.")

            # ROUTE: Calls GstDataDecryptor using mode 'sek'
            decrypted_sek = call_java_standalone_decryptor(
                "sek", input_app_key, target_sek, java_folder_dir
            )

            print("\n" + "✅" * 20 + "\n 🎉 AUTH RESPONSE DECRYPTION SUCCESSFUL!\n" + "=" * 60)
            print(f"Auth Token Context:    {target_token}")
            print(f"Session Expiry Info:   {target_expiry} minutes")
            print(f"Decrypted Base64 SEK:  {decrypted_sek}")
            print("=" * 60)

        # --------------------------------------------------
        # WORKFLOW OPTION 4: SEPARATE FIELD MANUAL AUTH DECRYPTION
        # --------------------------------------------------
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

            # ROUTE: Calls GstDataDecryptor using mode 'sek'
            decrypted_sek = call_java_standalone_decryptor(
                "sek", input_app_key, received_sek, java_folder_dir
            )

            print("\n" + "✅" * 20 + "\n 🎉 AUTH FIELD DECRYPTION SUCCESSFUL!\n" + "=" * 60)
            print(f"Your Auth Token:       {received_auth_token}")
            print(f"Session Expiry:        {received_expiry} minutes")
            print(f"Decrypted Base64 SEK:  {decrypted_sek}")
            print("=" * 60)

        # --------------------------------------------------
        # WORKFLOW OPTION 5: TRANSACTIONAL BUSINESS DATA DECRYPTION (NEW)
        # --------------------------------------------------
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

            # Parse the JSON to extract rek and data separately
            try:
                parsed = json.loads(encrypted_response_json)
                rek = parsed.get("rek", "")
                data = parsed.get("data", "")
                if not rek or not data:
                    raise ValueError("Response JSON must contain 'rek' and 'data' fields.")
            except json.JSONDecodeError:
                raise ValueError("Invalid JSON input.")

            # ROUTE: Calls GstDataDecryptor using mode 'api_response' with rek and data as separate args
            decrypted_json_data = call_java_standalone_decryptor(
                "api_response", input_decrypted_sek, rek, java_folder_dir, data
            )

            print(
                "\n" + "✅" * 20 + "\n 📦 DECRYPTED TRANSACTONAL DATA BLOCK ATTACHED:\n" + "=" * 60
            )
            try:
                # Try formatting to look clean if it returned a pure string dictionary
                print(json.dumps(json.loads(decrypted_json_data), indent=2))
            except:
                print(decrypted_json_data)
            print("=" * 60)

        else:
            print("\n❌ Invalid choice selected. Please restart script and use options 1 to 5.")

    except Exception as e:
        print(f"\n🚨 Error executing framework orchestration: {e}")
