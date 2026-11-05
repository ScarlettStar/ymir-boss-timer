package com.scarlettstar.ymir;
import android.app.*;
import android.content.*;
import android.os.*;
import androidx.test.ext.junit.runners.AndroidJUnit4;
import androidx.test.platform.app.InstrumentationRegistry;
import androidx.test.rule.ActivityTestRule;
import org.json.*;
import org.junit.*;
import org.junit.runner.RunWith;
import java.io.*;
import static org.junit.Assert.*;
@RunWith(AndroidJUnit4.class)
public class AndroidTimerTest {
    @Rule public ActivityTestRule<MainActivity> activity=new ActivityTestRule<>(MainActivity.class);
    private Context context(){return InstrumentationRegistry.getInstrumentation().getTargetContext();}
    @Test public void desktopZipRoundTripAndRejectedImportPreserveData()throws Exception {
        Store store=new Store(context());JSONObject state=Store.empty();JSONObject b=TimerModel.newBoss("Guardião",180,TimerModel.REGIONS[1],"CHN 2","Elite","default",true);TimerModel.kill(b,System.currentTimeMillis()/1000.0);state.getJSONArray("bosses").put(b);store.write(state);
        ByteArrayOutputStream bytes=new ByteArrayOutputStream();Store.exportState(state,bytes);
        JSONObject imported=Store.parseBackup(new ByteArrayInputStream(bytes.toByteArray()));assertEquals("Guardião",imported.getJSONArray("bosses").getJSONObject(0).getString("name"));assertEquals(b.getDouble("end"),imported.getJSONArray("bosses").getJSONObject(0).getDouble("end"),0);
        store.importState(imported);assertTrue(new File(context().getFilesDir(),"backups").list().length>0);
        JSONObject invalid=new JSONObject(imported.toString());invalid.getJSONArray("bosses").getJSONObject(0).put("minutes",0);
        assertThrows(IllegalArgumentException.class,()->store.importState(invalid));assertEquals(180,store.read().getJSONArray("bosses").getJSONObject(0).getInt("minutes"));
        AlarmScheduler.reschedule(context(),store.read());
        // Unique URI identities prevent collisions across accounts even with identical boss IDs.
        JSONObject other=new JSONObject(b.toString()).put("profile_id","other");assertNotEquals(AlarmScheduler.pending(context(),b),AlarmScheduler.pending(context(),other));
    }
    @Test public void systemAlarmPostsNotificationWithActivityInBackground()throws Exception {
        Context c=context();Instrumentation instrumentation=InstrumentationRegistry.getInstrumentation();
        if(Build.VERSION.SDK_INT>=33)instrumentation.getUiAutomation().executeShellCommand("pm grant "+c.getPackageName()+" android.permission.POST_NOTIFICATIONS").close();
        if(Build.VERSION.SDK_INT>=31)instrumentation.getUiAutomation().executeShellCommand("appops set "+c.getPackageName()+" SCHEDULE_EXACT_ALARM allow").close();
        Thread.sleep(700);AlarmReceiver.channels(c);c.getSystemService(NotificationManager.class).cancelAll();
        instrumentation.runOnMainSync(()->activity.getActivity().moveTaskToBack(true));
        AlarmScheduler.test(c);
        long until=System.currentTimeMillis()+25000;boolean found=false;
        while(System.currentTimeMillis()<until){for(android.service.notification.StatusBarNotification n:c.getSystemService(NotificationManager.class).getActiveNotifications())if("test".equals(n.getTag()))found=true;if(found)break;Thread.sleep(500);}
        assertTrue("AlarmManager must deliver while Activity is backgrounded",found);
        assertEquals("Ymir • teste de alerta",c.getSystemService(NotificationManager.class).getActiveNotifications()[0].getNotification().extras.getString(Notification.EXTRA_TITLE));
    }
}
