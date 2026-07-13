import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.security.Key;
import java.util.Base64;

public class GstDataDecryptor {

    public static void main(String[] args) {
        if (args.length < 3) {
            System.err.println("Error: Missing arguments.");
            System.err.println("Usage: java GstDataDecryptor \"<mode>\" \"<encryption_key>\" \"<encrypted_data>\"");
            System.err.println("       java GstDataDecryptor api_response \"<decrypted_sek(b64)>\" \"<rek>\" \"<data>\"");
            System.err.println("Modes: 'sek' (decrypt SEK with raw app_key), 'api_response' (two-step GST decrypt)");
            System.exit(1);
        }

        String mode = args[0].toLowerCase();
        String keyString = args[1];
        String encryptedData = args[2];

        try {
            if ("sek".equals(mode)) {
                // SEK decryption uses the unencrypted raw 32-character app_key string bytes directly
                byte[] keyBytes = keyString.getBytes("UTF-8");
                Key aesKey = new SecretKeySpec(keyBytes, "AES");
                Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
                cipher.init(Cipher.DECRYPT_MODE, aesKey);
                byte[] decryptedBytes = cipher.doFinal(Base64.getDecoder().decode(encryptedData));
                // Output base64-encoded so it can be safely passed to api_response mode
                System.out.print(Base64.getEncoder().encodeToString(decryptedBytes));

            } else if ("api_response".equals(mode)) {
                // Two-step GST API response decryption.
                // Args: keyString = decrypted SEK (base64), encryptedData = rek (base64), args[3] = data (base64)
                if (args.length < 4) {
                    System.err.println("Error: api_response mode requires 4 args: mode decrypted_sek rek data");
                    System.exit(1);
                }
                String rekEncrypted = encryptedData;
                String dataEncrypted = args[3];

                byte[] ekBytes = Base64.getDecoder().decode(keyString); // decrypted SEK = EK (raw bytes)

                // Step 1: decrypt rek with EK to get data_key
                Key ekKey = new SecretKeySpec(ekBytes, "AES");
                Cipher rekCipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
                rekCipher.init(Cipher.DECRYPT_MODE, ekKey);
                byte[] dataKeyBytes = rekCipher.doFinal(Base64.getDecoder().decode(rekEncrypted));

                // Step 2: decrypt data with data_key
                Key dataKey = new SecretKeySpec(dataKeyBytes, "AES");
                Cipher dataCipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
                dataCipher.init(Cipher.DECRYPT_MODE, dataKey);
                byte[] decryptedDataBytes = dataCipher.doFinal(Base64.getDecoder().decode(dataEncrypted));
                String result = new String(Base64.getDecoder().decode(decryptedDataBytes), "UTF-8");

                System.out.print(result);

            } else {
                System.err.println("Error: Invalid mode. Use 'sek' or 'api_response'.");
                System.exit(1);
            }

        } catch (Exception e) {
            System.err.println("Decryption Execution Error: " + e.getMessage());
            System.exit(1);
        }
    }
}