package com.scarlettstar.ymir;

import android.content.Context;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.nio.charset.StandardCharsets;
import java.util.*;
import java.util.zip.*;

public final class Store {
    private final Context context;
    private static final Map<String,String> NAMES = new LinkedHashMap<>();
    static {NAMES.put("bosses.json","bosses");NAMES.put("history.json","history");NAMES.put("profiles.json","profiles");NAMES.put("preferences.json","preferences");NAMES.put("updates.json","updates");}
    public Store(Context context) { this.context=context.getApplicationContext(); }
    private AtomicFile file() { return new AtomicFile(new File(context.getFilesDir(),"state.json")); }
    public static JSONObject empty() throws JSONException {
        JSONObject account=new JSONObject().put("id","default").put("name","Conta principal").put("server","").put("regions",new JSONArray());
        return new JSONObject().put("bosses",new JSONArray()).put("history",new JSONArray())
            .put("profiles",new JSONObject().put("version",1).put("active","default").put("profiles",new JSONArray().put(account)))
            .put("preferences",new JSONObject().put("lead_seconds",60)).put("updates",new JSONObject());
    }
    public synchronized JSONObject read() throws IOException,JSONException {
        if (!file().getBaseFile().exists() && !new File(context.getFilesDir(),"state.json.bak").exists()) return empty();
        JSONObject result=new JSONObject(new String(file().readFully(),StandardCharsets.UTF_8));
        TimerModel.validate(result);
        return result;
    }
    public synchronized void write(JSONObject state) throws IOException,JSONException {
        TimerModel.validate(state);
        FileOutputStream output=null;
        try { output=file().startWrite(); output.write(state.toString().getBytes(StandardCharsets.UTF_8)); file().finishWrite(output); }
        catch(IOException | RuntimeException e) { if(output!=null)file().failWrite(output); throw e; }
    }
    public static JSONObject find(JSONObject state,String pid,String id) throws JSONException {
        JSONArray bosses=state.getJSONArray("bosses");
        for(int i=0;i<bosses.length();i++) {
            JSONObject b=bosses.getJSONObject(i);
            if(TimerModel.profile(b).equals(pid) && b.getString("id").equals(id)) return b;
        }
        return null;
    }
    public static String identity(JSONObject state,JSONObject boss) throws JSONException {
        JSONArray accounts=state.getJSONObject("profiles").getJSONArray("profiles");
        for(int i=0;i<accounts.length();i++) {
            JSONObject p=accounts.getJSONObject(i);
            if(p.getString("id").equals(TimerModel.profile(boss))) return p.getString("name")+" / "+p.optString("server","");
        }
        return TimerModel.profile(boss);
    }
    public static JSONObject parseBackup(InputStream input) throws IOException,JSONException {
        JSONObject result=new JSONObject();
        Set<String> seen=new HashSet<>();
        try(ZipInputStream zip=new ZipInputStream(input,StandardCharsets.UTF_8)) {
            ZipEntry entry;
            int total=0;
            while((entry=zip.getNextEntry())!=null) {
                String name=entry.getName();
                if(!NAMES.containsKey(name) || !seen.add(name) || seen.size()>5 || entry.isDirectory()) throw new IOException("Arquivo inesperado no backup.");
                ByteArrayOutputStream data=new ByteArrayOutputStream();
                byte[] buffer=new byte[8192];int n;
                while((n=zip.read(buffer))!=-1) { total+=n;if(total>20_000_000)throw new IOException("Backup maior que 20 MB.");data.write(buffer,0,n); }
                String text=data.toString(StandardCharsets.UTF_8.name());
                result.put(NAMES.get(name),name.equals("bosses.json")||name.equals("history.json")?new JSONArray(text):new JSONObject(text));
            }
        }
        if(!result.has("preferences"))result.put("preferences",new JSONObject().put("lead_seconds",60));
        if(!result.has("updates"))result.put("updates",new JSONObject());
        TimerModel.validate(result);
        return result;
    }
    public void importState(JSONObject candidate) throws IOException,JSONException {
        TimerModel.validate(candidate);
        JSONObject current=read();
        File backups=new File(context.getFilesDir(),"backups");
        if(!backups.isDirectory() && !backups.mkdirs())throw new IOException("Não foi possível criar backup dos dados atuais.");
        File safety=new File(backups,"before-import-"+System.currentTimeMillis()+".zip");
        try(OutputStream out=new FileOutputStream(safety)) { exportState(current,out); }
        write(candidate);
        File[] old=backups.listFiles();
        if(old!=null) { Arrays.sort(old,Comparator.comparing(File::getName).reversed());for(int i=6;i<old.length;i++) { if(!old[i].delete())break; } }
    }
    public static void exportState(JSONObject state,OutputStream output) throws IOException,JSONException {
        TimerModel.validate(state);
        try(ZipOutputStream zip=new ZipOutputStream(output,StandardCharsets.UTF_8)) {
            for(Map.Entry<String,String> entry:NAMES.entrySet()) {
                if(!state.has(entry.getValue()))continue;
                zip.putNextEntry(new ZipEntry(entry.getKey()));
                zip.write(state.get(entry.getValue()).toString().getBytes(StandardCharsets.UTF_8));zip.closeEntry();
            }
        }
    }
}
