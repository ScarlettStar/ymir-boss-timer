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
        Store store=new Store(c);JSONObject state=Store.empty();
        JSONObject boss=TimerModel.newBoss("Guardião noturno",180,TimerModel.REGIONS[1],"CHN 2","Boss","default",true);
        double now=System.currentTimeMillis()/1000.0;boss.put("last_kill",now).put("end",now+10);
        state.getJSONArray("bosses").put(boss);state.getJSONObject("preferences").put("lead_seconds",0);
        store.write(state);AlarmScheduler.reschedule(c,state);
        String tag=TimerModel.key(boss);
        long until=System.currentTimeMillis()+25000;boolean found=false;
        while(System.currentTimeMillis()<until){for(android.service.notification.StatusBarNotification n:c.getSystemService(NotificationManager.class).getActiveNotifications())if(tag.equals(n.getTag()))found=true;if(found)break;Thread.sleep(500);}
        assertTrue("AlarmManager must deliver while Activity is backgrounded",found);
        Notification notification=c.getSystemService(NotificationManager.class).getActiveNotifications()[0].getNotification();
        assertTrue(notification.extras.getString(Notification.EXTRA_TITLE).contains("Guardião noturno"));
        assertTrue(notification.extras.getString(Notification.EXTRA_TEXT).contains("CHN 2"));
        JSONObject saved=store.read().getJSONArray("bosses").getJSONObject(0);
        assertEquals(saved.getDouble("end"),saved.getDouble("finished_for"),0);
    }
    @Test public void cloudSessionEncryptionAndReceivedTimerRemainLocalAfterReopen()throws Exception {
        Context c=context();Store store=new Store(c);JSONObject original=Store.empty();
        JSONObject boss=TimerModel.newBoss("Chefe recebido",60,TimerModel.REGIONS[1],"CHN 2","Boss","default",true);boss.put("id","cloud-test");TimerModel.kill(boss,System.currentTimeMillis()/1000.0);original.getJSONArray("bosses").put(boss);store.write(original);
        JSONObject received=CloudModel.copy(original);received.getJSONArray("bosses").getJSONObject(0).put("end",boss.getDouble("end")+300);
        JSONObject updated=CloudModel.apply(original,CloudModel.entities(received));store.importState(updated);AlarmScheduler.reschedule(c,updated);
        assertEquals(received.getJSONArray("bosses").getJSONObject(0).getDouble("end"),new Store(c).read().getJSONArray("bosses").getJSONObject(0).getDouble("end"),0);
        JSONObject session=new JSONObject().put("project","demo-ymir-test").put("api_key","not-a-real-key-1234567890").put("uid","test-user").put("refresh","private-test-token").put("email","test@example.invalid");
        try{
            CloudVault.write(c,session);assertEquals("private-test-token",CloudVault.read(c).getString("refresh"));
            java.nio.file.Path file=new File(c.getNoBackupFilesDir(),"cloud-session.bin").toPath();String ciphertext=new String(java.nio.file.Files.readAllBytes(file),java.nio.charset.StandardCharsets.UTF_8);assertFalse(ciphertext.contains("private-test-token"));
            ByteArrayOutputStream backup=new ByteArrayOutputStream();Store.exportState(store.read(),backup);JSONObject decoded=Store.parseBackup(new ByteArrayInputStream(backup.toByteArray()));assertFalse(decoded.toString().contains("private-test-token"));
        }finally{CloudVault.clear(c);}
    }
    private java.util.List<android.view.View> views(android.view.View root){
        java.util.List<android.view.View> all=new java.util.ArrayList<>();all.add(root);for(int i=0;i<all.size();i++){android.view.View v=all.get(i);if(v instanceof android.view.ViewGroup){android.view.ViewGroup group=(android.view.ViewGroup)v;for(int j=0;j<group.getChildCount();j++)all.add(group.getChildAt(j));}}return all;
    }
    private android.widget.Button findButton(String contains){for(android.view.View v:views(activity.getActivity().getWindow().getDecorView()))if(v instanceof android.widget.Button&&((android.widget.Button)v).getText().toString().contains(contains))return (android.widget.Button)v;throw new AssertionError("Button not found: "+contains);}
    private java.util.List<String> visibleRoleNames(){java.util.List<String> result=new java.util.ArrayList<>();java.util.Set<String> roles=new java.util.HashSet<>(java.util.Arrays.asList("Guerreiro","Lanceiro","Maga","Escald"));for(android.view.View v:views(activity.getActivity().getWindow().getDecorView()))if(v instanceof android.widget.TextView&&!(v instanceof android.widget.Button)&&!(v instanceof android.widget.EditText)){String text=((android.widget.TextView)v).getText().toString();if(roles.contains(text))result.add(text);}return result;}
    private void screen(String name)throws Exception {try(android.os.ParcelFileDescriptor fd=InstrumentationRegistry.getInstrumentation().getUiAutomation().executeShellCommand("screencap -p /sdcard/Download/"+name);java.io.InputStream input=new android.os.ParcelFileDescriptor.AutoCloseInputStream(fd)){byte[] bytes=new byte[8192];while(input.read(bytes)!=-1){/* Wait for the screenshot command to finish. */}}}
    @Test public void regionGroupsRoleOrderCollapseAndSearchPreserveAllTimerData()throws Exception {
        Context c=context();Instrumentation instrumentation=InstrumentationRegistry.getInstrumentation();JSONObject state=Store.empty();JSONArray all=state.getJSONArray("bosses");
        for(String floor:new String[]{"P1","P2","P3","P4 UNIVERSAL"})for(String role:new String[]{"Escald","Maga","Guerreiro","Lanceiro"}){JSONObject b=TimerModel.newBoss(role,120,TimerModel.REGIONS[2],"","Boss","default",false);b.put("floor",floor);TimerModel.kill(b,System.currentTimeMillis()/1000.0);all.put(b);}
        all.put(TimerModel.newBoss("Myrk teste",60,TimerModel.REGIONS[1],"CHN 1","Boss","default",true));all.put(TimerModel.newBoss("Myrk teste",60,TimerModel.REGIONS[1],"CHN 2","Boss","default",true));all.put(TimerModel.newBoss("Chefe do labirinto",60,"Labirinto Albit","","Boss","default",true));
        new Store(c).write(state);c.getSharedPreferences("catalog-layout",0).edit().clear().commit();
        instrumentation.runOnMainSync(()->{findButton("Bosses").performClick();assertEquals(16,visibleRoleNames().size());for(int i=0;i<16;i++)assertEquals(new String[]{"Guerreiro","Lanceiro","Maga","Escald"}[i%4],visibleRoleNames().get(i));findButton("Fólkvangr").performClick();assertEquals(0,visibleRoleNames().size());});
        assertTrue(CloudModel.equal(state,new Store(c).read()));
        instrumentation.runOnMainSync(()->{android.widget.EditText search=null;for(android.view.View v:views(activity.getActivity().getWindow().getDecorView()))if(v instanceof android.widget.EditText&&"Buscar boss, região ou canal".equals(((android.widget.EditText)v).getHint().toString()))search=(android.widget.EditText)v;assertNotNull(search);search.setText("Maga");assertEquals(java.util.Arrays.asList("Maga","Maga","Maga","Maga"),visibleRoleNames());search.setText("");assertEquals(0,visibleRoleNames().size());findButton("Myrkheimr").performClick();});
        instrumentation.waitForIdleSync();screen("ymir-regions.png");
        instrumentation.runOnMainSync(()->findButton("Fólkvangr").performClick());instrumentation.waitForIdleSync();screen("ymir-folk-order.png");assertTrue(CloudModel.equal(state,new Store(c).read()));
    }
}
