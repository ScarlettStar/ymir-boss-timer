package com.scarlettstar.ymir;
import android.content.*;
public final class RestoreAlarmsReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c,Intent intent) {
        String action=intent==null?null:intent.getAction();
        if (!Intent.ACTION_BOOT_COMPLETED.equals(action) && !Intent.ACTION_MY_PACKAGE_REPLACED.equals(action)
            && !Intent.ACTION_TIME_CHANGED.equals(action)
            && !android.app.AlarmManager.ACTION_SCHEDULE_EXACT_ALARM_PERMISSION_STATE_CHANGED.equals(action)) return;
        try { AlarmScheduler.reschedule(c,new Store(c).read()); CloudSync.schedule(c); }
        catch(Exception e) { android.util.Log.e("Ymir","Falha ao reagendar timers",e); }
    }
}
