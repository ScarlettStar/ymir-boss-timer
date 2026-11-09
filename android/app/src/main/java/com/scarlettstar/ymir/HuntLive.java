package com.scarlettstar.ymir;

import android.content.Context;
import android.os.*;
import org.json.*;
import java.net.URLEncoder;
import java.util.concurrent.*;

public final class HuntLive {
    private HuntLive() {}
    private static final ExecutorService NETWORK=Executors.newSingleThreadExecutor();
    private static final Handler MAIN=new Handler(Looper.getMainLooper());
    private static boolean busy=false;
    private static String identity="",token="",owner="";
    private static long tokenUntil=0;
    public static JSONArray rows=new JSONArray();
    public static String status="Conecte o mesmo login do Boss Auto em Ajustes → Nuvem.";
    public interface Done {void done();}
    public static JSONArray visibleRows(Context c){
        try{JSONObject s=CloudVault.read(c);if(s!=null&&owner.equals(s.getString("project")+":"+s.getString("uid")))return rows;}catch(Exception ignored){}
        return new JSONArray();
    }
    public static void clear(){rows=new JSONArray();owner="";token="";tokenUntil=0;}
    public static void refresh(Context context,Done done){
        if(busy)return;Context c=context.getApplicationContext();final JSONObject session;
        try{session=CloudVault.read(c);if(session==null){rows=new JSONArray();status="Nuvem desconectada.";done.done();return;}}catch(Exception e){status="Entre novamente na nuvem.";done.done();return;}
        busy=true;
        NETWORK.execute(()->{try{
            String uid=session.getString("uid"),project=session.getString("project"),id=project+":"+uid;
            if(!id.equals(identity)||System.currentTimeMillis()>=tokenUntil){
                JSONObject auth=CloudSync.request("https://securetoken.googleapis.com/v1/token?key="+session.getString("api_key"),"POST",new JSONObject().put("refresh_token",session.getString("refresh")),null,true);
                if(!auth.getString("user_id").equals(uid))throw new IllegalArgumentException("Sessão de outra conta.");
                token=auth.getString("id_token");identity=id;tokenUntil=System.currentTimeMillis()+3000000;
            }
            String url="https://firestore.googleapis.com/v1/projects/"+project+"/databases/(default)/documents/users/"+URLEncoder.encode(uid,"UTF-8")+"/automation?pageSize=20&orderBy=receivedAt%20desc";
            JSONObject response=CloudSync.request(url,"GET",null,token,false);JSONArray documents=response.optJSONArray("documents"),result=new JSONArray();
            if(documents!=null)for(int i=0;i<documents.length();i++){
                try{JSONObject fields=documents.getJSONObject(i).getJSONObject("fields"),value=HuntLiveModel.validate(new JSONObject(fields.getJSONObject("payload").getString("stringValue")));
                    double stamp=java.time.Instant.parse(fields.getJSONObject("receivedAt").getString("timestampValue")).toEpochMilli()/1000.0;
                    result.put(value.put("received_at",stamp));}catch(Exception ignored){/* Invalid rows never look live. */}
            }
            MAIN.post(()->{busy=false;try{JSONObject current=CloudVault.read(c);if(current!=null&&current.getString("uid").equals(uid)&&current.getString("project").equals(project)){rows=result;owner=project+":"+uid;status="Atualizações a cada 15s nesta aba. Dados antigos são identificados.";}}catch(Exception ignored){}done.done();});
        }catch(Exception e){MAIN.post(()->{busy=false;status=e.getMessage()==null?"Sem conexão; última atividade mantida com horário.":e.getMessage();done.done();});}});
    }
}
