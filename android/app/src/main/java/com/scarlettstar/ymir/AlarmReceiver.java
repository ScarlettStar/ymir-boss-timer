package com.scarlettstar.ymir;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.os.Build;
import org.json.*;

public final class AlarmReceiver extends BroadcastReceiver {
    public static final String CHANNEL="respawn-v1";
    public static void channels(Context c) {
        NotificationChannel channel=new NotificationChannel(CHANNEL,"Alertas de bosses",NotificationManager.IMPORTANCE_HIGH);
        channel.setDescription("Boss, conta, servidor e canal. Configure som e vibração aqui.");
        channel.enableVibration(true);
        c.getSystemService(NotificationManager.class).createNotificationChannel(channel);
    }
    public static boolean notificationsEnabled(Context c) {
        channels(c);
        if(Build.VERSION.SDK_INT>=33 && c.checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)return false;
        NotificationManager manager=c.getSystemService(NotificationManager.class);
        return manager.areNotificationsEnabled() && manager.getNotificationChannel(CHANNEL).getImportance()!=NotificationManager.IMPORTANCE_NONE;
    }
    @android.annotation.SuppressLint("MissingPermission") // notificationsEnabled performs API 33 permission check.
    public static void show(Context c,String tag,String title,String text) {
        channels(c);
        if(!notificationsEnabled(c))return;
        Intent open=new Intent(c,MainActivity.class).setData(android.net.Uri.parse("ymir://open/"+android.net.Uri.encode(tag)));
        PendingIntent content=PendingIntent.getActivity(c,0,open,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
        Notification notification=new Notification.Builder(c,CHANNEL).setSmallIcon(com.scarlettstar.ymir.R.drawable.ic_boss)
            .setContentTitle(title).setContentText(text).setStyle(new Notification.BigTextStyle().bigText(text))
            .setContentIntent(content).setAutoCancel(true).setCategory(Notification.CATEGORY_REMINDER)
            .setVisibility(Notification.VISIBILITY_PRIVATE).setShowWhen(true).build();
        c.getSystemService(NotificationManager.class).notify(tag,1,notification);
    }
    @Override public void onReceive(Context context,Intent intent) {
        if("com.scarlettstar.ymir.TEST".equals(intent.getAction())) {
            show(context,"test","Ymir • teste de alerta","O aviso foi disparado pelo Android. Os timers não foram alterados.");return;
        }
        try {
            Store store=new Store(context);
            JSONObject state=store.read(), boss=Store.find(state,intent.getStringExtra("profile"),intent.getStringExtra("boss"));
            if(boss==null)return;
            double now=System.currentTimeMillis()/1000.0, end=boss.optDouble("end",0);
            if(end<=0 || boss.optDouble("finished_for",0)==end)return;
            boolean finished=now>=end;
            if(!finished && (boss.optDouble("warned_for",0)==end || end-now>TimerModel.lead(state.getJSONObject("preferences"),boss)+2))return;
            boss.put(finished?"finished_for":"warned_for",end);
            store.write(state);
            if(!TimerModel.muted(state.getJSONObject("preferences"),boss,now)) {
                String title=(boss.optBoolean("variable_respawn")?"Previsão: ":"")+boss.getString("name")+(finished?" • horário de respawn":" • vai nascer em breve");
                String text=Store.identity(state,boss)+"\n"+TimerModel.location(boss)+(boss.optBoolean("variable_respawn")?"\nEstimativa; confirme o reaparecimento no jogo.":"");
                show(context,TimerModel.key(boss),title,text);
            }
            AlarmScheduler.reschedule(context,state);
        } catch(Exception e) {
            android.util.Log.e("Ymir","Não foi possível processar o alerta",e);
        }
    }
}
