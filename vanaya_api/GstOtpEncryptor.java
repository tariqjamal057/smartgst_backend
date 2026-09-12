import java.io.File;
import java.io.FileInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.security.Key;
import java.security.KeyFactory;
import java.security.PublicKey;
import java.security.spec.X509EncodedKeySpec;
import javax.crypto.Cipher;
import javax.crypto.spec.SecretKeySpec;
import java.util.Base64;

public class GstOtpEncryptor {

    // Permanently set to your official sandbox validation variable
    private static final String FIXED_OTP = "575757";

    public static void main(String[] args) {
        // Decryption operational branch
        if (args.length == 3 && "decrypt_sek".equalsIgnoreCase(args[0])) {
            String rawAppKeyString = args[1];
            String encryptedSek = args[2];
            try {
                String decryptedSek = decryptSEK(encryptedSek, rawAppKeyString.getBytes("UTF-8"));
                System.out.print(decryptedSek);
            } catch (Exception e) {
                System.err.print("Decryption Error: " + e.getMessage());
                System.exit(1);
            }
            return;
        }

        // Arguments Check for general encryption flows
        if (args.length < 5) {
            System.err.println("Error: Missing arguments.");
            System.err.println("Usage: java GstOtpEncryptor \"<action>\" \"<username>\" \"<gst_public_key_path>\" \"<raw_app_key>\" \"<output_type>\" [\"<otp>\"]");
            System.exit(1);
        }

        String action = args[0];
        String userName = args[1];
        String publicKeyPath = args[2];
        String rawAppKeyString = args[3];
        String outputType = args[4];
        // Optional 6th argument: the OTP to encrypt. Falls back to FIXED_OTP.
        String otp = args.length > 5 ? args[5] : FIXED_OTP;

        try {
            byte[] bytesData = rawAppKeyString.getBytes("UTF-8");

            // 1. Asymmetric RSA App Key Encryption
            PublicKey publicKey = readPemPublicKey(publicKeyPath);
            Cipher rsaCipher = Cipher.getInstance("RSA");
            rsaCipher.init(Cipher.ENCRYPT_MODE, publicKey);
            byte[] encryptedAppKeyBytes = rsaCipher.doFinal(bytesData);
            String encryptedAppKey = Base64.getEncoder().encodeToString(encryptedAppKeyBytes);

            // 2. Symmetric AES OTP Encryption using the raw byte block
            Key aesKey = new SecretKeySpec(bytesData, "AES");
            Cipher aesCipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
            aesCipher.init(Cipher.ENCRYPT_MODE, aesKey);
            byte[] encryptedOtpBytes = aesCipher.doFinal(otp.getBytes("UTF-8"));
            String encryptedOtp = Base64.getEncoder().encodeToString(encryptedOtpBytes);

            // 3. Selective programmatic return routing
            if ("app_key".equalsIgnoreCase(outputType)) {
                System.out.print(encryptedAppKey);
            } else if ("otp".equalsIgnoreCase(outputType)) {
                System.out.print(encryptedOtp);
            } else {
                String payload = "{\"action\":\"" + action + "\",\"username\":\"" + userName + "\",\"app_key\":\"" + encryptedAppKey + "\",\"otp\":\"" + encryptedOtp + "\"}";
                System.out.print(payload);
            }

        } catch (Exception e) {
            System.err.println("Encryption Error: " + e.getMessage());
            System.exit(1);
        }
    }

    public static String decryptSEK(String encryptedSek, byte[] apikey) throws Exception {
        Key aesKey = new SecretKeySpec(apikey, "AES");
        Cipher cipher = Cipher.getInstance("AES/ECB/PKCS5Padding");
        cipher.init(Cipher.DECRYPT_MODE, aesKey);
        byte[] decryptedSekBytes = cipher.doFinal(Base64.getDecoder().decode(encryptedSek));
        return Base64.getEncoder().encodeToString(decryptedSekBytes);
    }

    private static PublicKey readPemPublicKey(String publicKeyPath) throws Exception {
        File file = new File(publicKeyPath);
        byte[] keyBytes = new byte[(int) file.length()];
        try (DataInputStream is = new DataInputStream(new FileInputStream(file))) {
            is.readFully(keyBytes);
        }
        
        String temp = new String(keyBytes, "UTF-8");
        String publicKeyPEM = temp
                .replaceAll("-----BEGIN[^-\n\r]*-----", "")
                .replaceAll("-----END[^-\n\r]*-----", "")
                .replaceAll("\\s+", "");

        byte[] decoded = Base64.getDecoder().decode(publicKeyPEM);
        X509EncodedKeySpec spec = new X509EncodedKeySpec(decoded);
        KeyFactory kf = KeyFactory.getInstance("RSA");
        return kf.generatePublic(spec);
    }
}