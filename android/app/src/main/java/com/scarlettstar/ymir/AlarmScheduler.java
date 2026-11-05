package com.scarlettstar.ymir;

import android.app.*;
import android.content.*;
import android.net.Uri;
import android.os.Build;
import org.json.*;
import java.util.*;

public final class AlarmScheduler {
    private AlarmScheduler() {}
    public static PendingIntent pending(Context c,JSONObject boss) throws JSONException {
        Intent intent=new Intent(c,AlarmReceiver.class).setAction("com.scarlettstar.ymir.RESPAWN")
            .setData(new Uri.Builder().scheme("ymir").authority("boss").appendPath(TimerModel.profile(boss)).appendPath(boss.getString("id")).build())
            .putExtra("profile",TimerModel.profile(boss)).putExtra("boss",boss.getString("id"));
        return PendingIntent.getBroadcast(c,0,intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE);
    }
    public static boolean exact(Context c) { return Build.VERSION.SDK_INT<31 || c.getSystemService(AlarmManager.class).canScheduleExactAlarms(); }
    @android.annotation.SuppressLint("ScheduleExactAlarm") // Runtime permission checked; revocation is caught.
    private static void schedule(Context c,long when,PendingIntent intent) {
        AlarmManager alarms=c.getSystemService(AlarmManager.class);
        try {
            if(exact(c))alarms.setExactAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,when,intent);
            else alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,when,intent);
        } catch(SecurityException denied) { alarms.setAndAllowWhileIdle(AlarmManager.RTC_WAKEUP,when,intent); }
    }
    public static long nextTime(JSONObject prefs,JSONObject boss,double now) {
        double end=boss.optDouble("end",0);
        if(end<=0 || boss.optDouble("finished_for",0)==end || end<now-900)return 0;
        int lead=TimerModel.lead(prefs,boss);
        double warning=end-lead;
        if(lead>0 && boss.optDouble("warned_for",0)!=end && end>now)return Math.max((long)Math.ceil(warning*1000),(long)(now*1000)+1000);
        return Math.max((long)Math.ceil(end*1000), (long)(now*1000)+1000);
    }
    public static void reschedule(Context c,JSONObject state) throws JSONException {
        AlarmManager alarms=c.getSystemService(AlarmManager.class);
        Set<String> current=new HashSet<>();
        JSONArray bosses=state.getJSONArray("bosses");
        for(int i=0;i<bosses.length();i++) {
            JSONObject b=bosses.getJSONObject(i);
            PendingIntent pending=pending(c,b);
            current.add(TimerModel.key(b));
            alarms.cancel(pending);
            long next=nextTime(state.getJSONObject("preferences"),b,System.currentTimeMillis()/1000.0);
            if(next>0)schedule(c,next,pending);
        }
        Set<String> previous=c.getSharedPreferences("alarms",0).getStringSet("keys",new HashSet<>());
        for(String key:previous) if(!current.contains(key)) {
            JSONArray pair=new JSONArray(key);
            alarms.cancel(pending(c,new JSONObject().put("profile_id",pair.getString(0)).put("id",pair.getString(1))));
        }
        c.getSharedPreferences("alarms",0).edit().putStringSet("keys",current).apply();
    }
    public static void test(Context c) {
        Intent intent=new Intent(c,AlarmReceiver.class).setAction("com.scarlettstar.ymir.TEST").setData(Uri.parse("ymir://test"));
        schedule(c,System.currentTimeMillis()+10000,PendingIntent.getBroadcast(c,0,intent,PendingIntent.FLAG_UPDATE_CURRENT|PendingIntent.FLAG_IMMUTABLE));
    }
}
