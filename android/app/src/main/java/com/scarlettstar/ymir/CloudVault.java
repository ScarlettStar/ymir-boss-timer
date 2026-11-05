package com.scarlettstar.ymir;

import android.content.Context;
import android.security.keystore.*;
import android.util.*;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.security.KeyStore;
import javax.crypto.*;
import javax.crypto.spec.GCMParameterSpec;

/** Refresh tokens encrypted by a non-exportable Android Keystore key, excluded from backup. */
final class CloudVault {
    private static javax.crypto.SecretKey key()throws Exception {
        KeyStore store=KeyStore.getInstance("AndroidKeyStore");store.load(null);
        if(!store.containsAlias("ymir-cloud")){KeyGenerator generator=KeyGenerator.getInstance(KeyProperties.KEY_ALGORITHM_AES,"AndroidKeyStore");generator.init(new KeyGenParameterSpec.Builder("ymir-cloud",KeyProperties.PURPOSE_ENCRYPT|KeyProperties.PURPOSE_DECRYPT).setBlockModes(KeyProperties.BLOCK_MODE_GCM).setEncryptionPaddings(KeyProperties.ENCRYPTION_PADDING_NONE).build());generator.generateKey();}
        return (javax.crypto.SecretKey)store.getKey("ymir-cloud",null);
    }
    private static AtomicFile file(Context c){return new AtomicFile(new File(c.getNoBackupFilesDir(),"cloud-session.bin"));}
    static JSONObject read(Context c)throws Exception {
        if(!file(c).getBaseFile().exists())return null;
        JSONObject envelope=new JSONObject(new String(file(c).readFully(),StandardCharsets.UTF_8));Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.DECRYPT_MODE,key(),new GCMParameterSpec(128,Base64.decode(envelope.getString("iv"),Base64.NO_WRAP)));
        return new JSONObject(new String(cipher.doFinal(Base64.decode(envelope.getString("data"),Base64.NO_WRAP)),StandardCharsets.UTF_8));
    }
    static void write(Context c,JSONObject session)throws Exception {
        Cipher cipher=Cipher.getInstance("AES/GCM/NoPadding");cipher.init(Cipher.ENCRYPT_MODE,key());
        JSONObject envelope=new JSONObject().put("iv",Base64.encodeToString(cipher.getIV(),Base64.NO_WRAP)).put("data",Base64.encodeToString(cipher.doFinal(session.toString().getBytes(StandardCharsets.UTF_8)),Base64.NO_WRAP));
        FileOutputStream output=null;AtomicFile file=file(c);try{output=file.startWrite();output.write(envelope.toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(output);}catch(Exception e){if(output!=null)file.failWrite(output);throw e;}
    }
    static void clear(Context c){file(c).delete();}
}
