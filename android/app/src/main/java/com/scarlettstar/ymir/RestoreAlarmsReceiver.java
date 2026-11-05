package com.scarlettstar.ymir;
import android.content.*;
public final class RestoreAlarmsReceiver extends BroadcastReceiver {
    @Override public void onReceive(Context c,Intent intent) {
        try { AlarmScheduler.reschedule(c,new Store(c).read()); }
        catch(Exception e) { android.util.Log.e("Ymir","Falha ao reagendar timers",e); }
    }
}
