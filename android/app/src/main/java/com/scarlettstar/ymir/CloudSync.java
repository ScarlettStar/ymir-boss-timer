package com.scarlettstar.ymir;

import android.app.job.*;
import android.content.*;
import android.os.*;
import android.util.AtomicFile;
import org.json.*;
import java.io.*;
import java.net.*;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.*;

public final class CloudSync {
    private static final ExecutorService NETWORK=Executors.newSingleThreadExecutor();
    private static final Handler MAIN=new Handler(Looper.getMainLooper());
    private static boolean busy=false;
    private static long next=0;
    public static String status="Nuvem desconectada • dados locais";
    public interface Done {void done(boolean success);}
    private static final int JOB=4312;
    private CloudSync() {}
    private static final class HttpError extends IOException {final int code;HttpError(int n){super(n==403?"Acesso negado. Confira as regras do Firebase.":n==429?"Limite temporário atingido. Tentaremos depois.":n==401?"Sessão expirada. Entre novamente.":"Não foi possível conectar à nuvem ("+n+").");code=n;}}
    private static JSONObject request(String url,String method,JSONObject data,String token,boolean form)throws Exception {
        HttpURLConnection connection=(HttpURLConnection)new URL(url).openConnection();connection.setConnectTimeout(20000);connection.setReadTimeout(20000);connection.setInstanceFollowRedirects(false);connection.setRequestMethod(method);
        connection.setRequestProperty("Content-Type",form?"application/x-www-form-urlencoded":"application/json");if(token!=null)connection.setRequestProperty("Authorization","Bearer "+token);
        try{
            if(data!=null){connection.setDoOutput(true);String text=data.toString();if(form)text="grant_type=refresh_token&refresh_token="+URLEncoder.encode(data.getString("refresh_token"),"UTF-8");try(OutputStream out=connection.getOutputStream()){out.write(text.getBytes(StandardCharsets.UTF_8));}}
            int code=connection.getResponseCode();if(code<200||code>=300)throw new HttpError(code);
            ByteArrayOutputStream buffer=new ByteArrayOutputStream();try(InputStream input=connection.getInputStream()){byte[] bytes=new byte[8192];int n;while((n=input.read(bytes))!=-1){if(buffer.size()+n>2_000_000)throw new IOException("Resposta muito grande.");buffer.write(bytes,0,n);}}
            return new JSONObject(buffer.toString("UTF-8"));
        }finally{connection.disconnect();}
    }
    public static void validateConfig(String project,String api)throws Exception {if(!project.matches("[a-z][a-z0-9-]{4,62}")||!api.matches("[A-Za-z0-9_-]{20,100}"))throw new IllegalArgumentException("Informe o ID do projeto e a Web API Key do Firebase.");}
    static JSONObject baseline(Context c,JSONObject session)throws Exception {
        AtomicFile file=new AtomicFile(new File(c.getNoBackupFilesDir(),"cloud-base.json"));
        if(file.getBaseFile().exists()){JSONObject saved=new JSONObject(new String(file.readFully(),StandardCharsets.UTF_8));if(saved.optString("project").equals(session.getString("project"))&&saved.optString("uid").equals(session.getString("uid")))return saved;}
        return new JSONObject().put("base",new JSONObject()).put("conflicts",new JSONArray());
    }
    static void saveBase(Context c,JSONObject session,JSONObject remote,JSONArray conflicts)throws Exception {
        JSONArray old=baseline(c,session).getJSONArray("conflicts"),all=new JSONArray();for(int i=Math.max(0,old.length()+conflicts.length()-100);i<old.length();i++)all.put(old.get(i));for(int i=Math.max(0,conflicts.length()-100);i<conflicts.length();i++)all.put(conflicts.get(i));
        JSONObject value=new JSONObject().put("project",session.getString("project")).put("uid",session.getString("uid")).put("base",remote).put("conflicts",all);
        AtomicFile file=new AtomicFile(new File(c.getNoBackupFilesDir(),"cloud-base.json"));FileOutputStream out=null;try{out=file.startWrite();out.write(value.toString().getBytes(StandardCharsets.UTF_8));file.finishWrite(out);}catch(Exception e){if(out!=null)file.failWrite(out);throw e;}
    }
    public static boolean connected(Context c){try{return CloudVault.read(c)!=null;}catch(Exception e){return false;}}
    public static JSONObject settings(Context c){try{JSONObject session=CloudVault.read(c);return session==null?new JSONObject():new JSONObject().put("project",session.getString("project")).put("api_key",session.getString("api_key")).put("email",session.getString("email"));}catch(Exception e){return new JSONObject();}}
    public static void login(Context context,String project,String api,String email,String password,boolean create,Done done){
        if(busy){done.done(false);return;}Context c=context.getApplicationContext();busy=true;status="Conectando…";
        NETWORK.execute(()->{try{validateConfig(project,api);JSONObject auth=request("https://identitytoolkit.googleapis.com/v1/accounts:"+(create?"signUp":"signInWithPassword")+"?key="+api,"POST",new JSONObject().put("email",email.trim()).put("password",password).put("returnSecureToken",true),null,false);
            JSONObject session=new JSONObject().put("project",project).put("api_key",api).put("email",email.trim()).put("uid",auth.getString("localId")).put("refresh",auth.getString("refreshToken"));
            MAIN.post(()->{try{CloudVault.write(c,session);schedule(c);next=0;status="Conectado • aguardando sincronização";busy=false;done.done(true);sync(c,true,null);}catch(Exception e){busy=false;status="Não foi possível salvar a sessão protegida.";done.done(false);}});
        }catch(Exception e){MAIN.post(()->{busy=false;status="Não foi possível entrar. Confira e-mail, senha e configuração.";done.done(false);});}});
    }
    public static void disconnect(Context c){if(busy)return;CloudVault.clear(c);c.getSystemService(JobScheduler.class).cancel(JOB);status="Desconectado • timers locais ativos";}
    public static void schedule(Context c){if(!connected(c))return;c.getSystemService(JobScheduler.class).schedule(new JobInfo.Builder(JOB,new ComponentName(c,CloudJob.class)).setRequiredNetworkType(JobInfo.NETWORK_TYPE_ANY).setPeriodic(15*60*1000L).setPersisted(true).build());}
    public static void sync(Context context,boolean force,Done callback){
        if(busy||(!force&&System.currentTimeMillis()<next)){if(callback!=null)callback.done(false);return;}
        Context c=context.getApplicationContext();final JSONObject session,snapshot,base;
        try{session=CloudVault.read(c);if(session==null){if(callback!=null)callback.done(true);return;}snapshot=new Store(c).read();base=baseline(c,session).getJSONObject("base");}catch(Exception e){status="Não foi possível ler dados de sincronização.";if(callback!=null)callback.done(false);return;}
        busy=true;next=System.currentTimeMillis()+60000;status="Sincronizando…";
        NETWORK.execute(()->{try{
            CloudModel.Merged result=exchange(session,base,CloudModel.entities(snapshot));
            MAIN.post(()->{try{
                Store store=new Store(c);JSONObject current=store.read();CloudModel.Merged rebased=CloudModel.merge(CloudModel.entities(snapshot),CloudModel.entities(current),result.records,true);JSONObject updated=CloudModel.apply(current,rebased.records);
                if(!CloudModel.equal(current,updated))store.importState(updated);
                saveBase(c,session,result.records,result.conflicts);AlarmScheduler.reschedule(c,updated);
                status="Sincronizado às "+new java.text.SimpleDateFormat("HH:mm:ss",java.util.Locale.getDefault()).format(new java.util.Date())+(result.conflicts.length()>0?" • conflito: mantido dado da nuvem; cópia local guardada":"");busy=false;if(callback!=null)callback.done(true);
            }catch(Exception e){busy=false;status="Falha ao salvar sincronização; nova tentativa pendente.";if(callback!=null)callback.done(false);}});
        }catch(Exception e){MAIN.post(()->{busy=false;status=e instanceof HttpError||e instanceof IllegalArgumentException?e.getMessage():"Sem sincronização. Marcações locais preservadas; tentaremos depois.";if(callback!=null)callback.done(false);});}});
    }
    private static CloudModel.Merged exchange(JSONObject session,JSONObject base,JSONObject local)throws Exception {
        String project=session.getString("project"),api=session.getString("api_key");validateConfig(project,api);
        JSONObject auth=request("https://securetoken.googleapis.com/v1/token?key="+api,"POST",new JSONObject().put("refresh_token",session.getString("refresh")),null,true);
        if(!auth.getString("user_id").equals(session.getString("uid")))throw new IOException("Sessão inválida.");String token=auth.getString("id_token");
        String url="https://firestore.googleapis.com/v1/projects/"+project+"/databases/(default)/documents/users/"+URLEncoder.encode(session.getString("uid"),"UTF-8")+"/sync/state";
        for(int attempt=0;attempt<4;attempt++){
            JSONObject remote;String condition;
            try{JSONObject document=request(url,"GET",null,token,false),fields=document.getJSONObject("fields");if(!fields.getJSONObject("schema").getString("integerValue").equals("1"))throw new IOException("Versão de nuvem incompatível.");String payload=fields.getJSONObject("payload").getString("stringValue");if(payload.getBytes(StandardCharsets.UTF_8).length>850000)throw new IOException("Nuvem muito grande.");remote=new JSONObject(payload);condition="currentDocument.updateTime="+URLEncoder.encode(document.getString("updateTime"),"UTF-8");}
            catch(HttpError error){if(error.code!=404)throw error;remote=new JSONObject();condition="currentDocument.exists=false";}
            CloudModel.validatePairing(base,local,remote);
            CloudModel.Merged merged=CloudModel.merge(base,local,remote,false);
            CloudModel.apply(Store.empty(),merged.records); // Validate before upload/application.
            if(CloudModel.equal(merged.records,remote))return merged;
            String payload=merged.records.toString();if(payload.getBytes(StandardCharsets.UTF_8).length>850000)throw new IOException("Dados excedem 850 KB; exporte backup e reduza histórico.");
            try{request(url+"?"+condition,"PATCH",new JSONObject().put("fields",new JSONObject().put("schema",new JSONObject().put("integerValue","1")).put("payload",new JSONObject().put("stringValue",payload))),token,false);return merged;}
            catch(HttpError e){if(e.code!=409&&e.code!=412&&e.code!=400)throw e;}
        }
        throw new IOException("Conflito simultâneo. Tentaremos depois.");
    }
}
