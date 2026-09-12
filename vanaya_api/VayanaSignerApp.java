import java.io.File;
import java.io.FileInputStream;
import java.io.DataInputStream;
import java.io.IOException;
import java.security.KeyFactory;
import java.security.PrivateKey;
import java.security.PublicKey;
import java.security.Signature;
import java.security.spec.PKCS8EncodedKeySpec;
import java.security.spec.X509EncodedKeySpec;
import javax.crypto.EncryptedPrivateKeyInfo;
import javax.crypto.SecretKeyFactory;
import javax.crypto.spec.PBEKeySpec;
import java.util.Base64;

public class VayanaSignerApp {

    public static void main(String[] args) {
        if (args.length < 2) {
            System.err.println("Error: Missing arguments.");
            System.err.println("Usage: java VayanaSignerApp \"<message>\" \"<private_key_path>\" [\"<password>\"]");
            System.exit(1);
        }

        String messageFromPython = args[0];
        String privateKeyPath = args[1];
        // Optional 3rd argument: the private key password. Falls back to the
        // hardcoded value only when not supplied (kept for CLI compatibility).
        String keyPassword = args.length > 2 ? args[2] : "Taxmate@123";

        try {
            VayanaSignerApp app = new VayanaSignerApp();
            PrivateKey privateKey = app.readPemPrivateKey(privateKeyPath, keyPassword);
            String signature = app.sign(messageFromPython, privateKey);
            
            // Output ONLY the raw signature to standard output for Python
            System.out.print(signature);
            
        } catch (Exception e) {
            System.err.println("Execution Error: " + e.getMessage());
            e.printStackTrace();
            System.exit(1);
        }
    }

    private PrivateKey readPemPrivateKey(String privateKeyPath, String password) throws Exception {
        File file = new File(privateKeyPath);
        byte[] keyBytes = new byte[(int) file.length()];
        try (DataInputStream is = new DataInputStream(new FileInputStream(file))) {
            is.readFully(keyBytes);
        }
        
        String temp = new String(keyBytes, "UTF-8");
        
        // FIX: Strip out all PEM headers, footers, hyphens, and whitespace cleanly via regex
        String cleanKeyPEM = temp
                .replaceAll("-----BEGIN[^-\n\r]*-----", "")
                .replaceAll("-----END[^-\n\r]*-----", "")
                .replaceAll("\\s+", ""); // Removes all spacing blocks, tabs, and newlines

        Base64.Decoder b64 = Base64.getDecoder();
        byte[] decoded = b64.decode(cleanKeyPEM);

        // Explicitly check for ENCRYPTED format keywords to pass your password phase
        if (temp.contains("ENCRYPTED")) {
            char[] passChars = password == null ? new char[0] : password.toCharArray();
            EncryptedPrivateKeyInfo encKeyInfo = new EncryptedPrivateKeyInfo(decoded);
            SecretKeyFactory skf = SecretKeyFactory.getInstance(encKeyInfo.getAlgName());
            java.security.Key pbeKey = skf.generateSecret(new PBEKeySpec(passChars));
            PKCS8EncodedKeySpec spec = encKeyInfo.getKeySpec(pbeKey);
            KeyFactory kf = KeyFactory.getInstance("RSA");
            return kf.generatePrivate(spec);
        } else {
            PKCS8EncodedKeySpec spec = new PKCS8EncodedKeySpec(decoded);
            KeyFactory kf = KeyFactory.getInstance("RSA");
            return kf.generatePrivate(spec);
        }
    }

    private String sign(String message, PrivateKey privateKey) throws Exception {
        Signature sig = Signature.getInstance("SHA256withRSA");
        sig.initSign(privateKey);
        sig.update(message.getBytes("UTF-8"));
        byte[] signatureBytes = sig.sign();
        return Base64.getEncoder().encodeToString(signatureBytes);
    }

    private Boolean verify(String message, String signature, PublicKey publicKey) throws Exception {
        Signature sig = Signature.getInstance("SHA256withRSA");
        sig.initVerify(publicKey);
        sig.update(message.getBytes("UTF-8"));
        return sig.verify(Base64.getDecoder().decode(signature));
    }

    private PublicKey readPemPublicKey(String publicKeyPath) throws Exception {
        File file = new File(publicKeyPath);
        byte[] keyBytes = new byte[(int) file.length()];
        try (DataInputStream is = new DataInputStream(new FileInputStream(file))) {
            is.readFully(keyBytes);
        }
        String temp = new String(keyBytes, "UTF-8");
        String pubKeyPEM = temp
                .replaceAll("-----BEGIN[^-\n\r]*-----", "")
                .replaceAll("-----END[^-\n\r]*-----", "")
                .replaceAll("\\s+", "");
        
        X509EncodedKeySpec spec = new X509EncodedKeySpec(Base64.getDecoder().decode(pubKeyPEM));
        KeyFactory kf = KeyFactory.getInstance("RSA");
        return kf.generatePublic(spec);
    }
}