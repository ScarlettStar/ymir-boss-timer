package com.scarlettstar.ymir;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;
public class TimerModelTest {
    private JSONObject boss(String pid,String channel)throws Exception{return TimerModel.newBoss("Guardião",180,TimerModel.REGIONS[1],channel,"Boss",pid,true);}
    @Test public void independentAccountsAndChannels()throws Exception {
        JSONObject a=boss("one","CHN 1"), b=boss("one","CHN 2"), c=boss("two","CHN 1");
        JSONArray all=new JSONArray().put(a).put(b).put(c);TimerModel.kill(b,1000);
        assertEquals(0,a.getDouble("end"),0);assertEquals(0,c.getDouble("end"),0);
        assertEquals(11800,b.getDouble("end"),0);
        assertEquals(1,TimerModel.visible(all,"one","CHN 1").size());assertEquals(2,TimerModel.visible(all,"one","Todos").size());
    }
    @Test public void learningUsesObservedSpawnAndNotConsecutiveKills()throws Exception {
        JSONObject b=boss("one","CHN 1");TimerModel.kill(b,1000);TimerModel.kill(b,2000);
        assertEquals(0,TimerModel.stats(b)[0],0);TimerModel.observe(b,8000);
        assertEquals(6000,TimerModel.duration(b),0);TimerModel.kill(b,10000);TimerModel.observe(b,17200);
        assertArrayEquals(new double[]{2,6600,6000,7200},TimerModel.stats(b),0);
        TimerModel.kill(b,20000);assertEquals(26600,b.getDouble("end"),0);
    }
    @Test public void observationOnlyOncePerCycle()throws Exception {
        JSONObject b=boss("default","CHN 1");TimerModel.kill(b,1000);TimerModel.observe(b,2000);
        assertThrows(IllegalArgumentException.class,()->TimerModel.observe(b,2100));
        assertEquals(1,TimerModel.stats(b)[0],0);
    }
    @Test public void samplesBoundedToLastTwenty()throws Exception {
        JSONObject b=boss("default","CHN 1");for(int i=1;i<=25;i++){TimerModel.kill(b,i*10000);TimerModel.observe(b,i*10000+3600);}
        assertEquals(20,b.getJSONArray("respawn_samples").length());assertEquals(3600,TimerModel.duration(b),0);
    }
    @Test public void invalidInputsAreRejected()throws Exception {
        assertThrows(IllegalArgumentException.class,()->TimerModel.newBoss("",1,"A","","Boss","default",false));
        assertThrows(IllegalArgumentException.class,()->TimerModel.newBoss("Boss",0,"A","","Boss","default",false));
        JSONObject b=boss("default","CHN 1");assertThrows(IllegalArgumentException.class,()->TimerModel.observe(b,1000));
        TimerModel.kill(b,2000);assertThrows(IllegalArgumentException.class,()->TimerModel.observe(b,1900));
    }
    @Test public void desktopPreferencesKeyIsCompatible()throws Exception {
        JSONObject b=boss("default","CHN 1");b.put("id","abc");assertEquals("[\"default\", \"abc\"]",TimerModel.key(b));
        JSONObject prefs=new JSONObject().put("lead_seconds",60).put("boss_alerts",new JSONObject().put("[\"default\", \"abc\"]",new JSONObject().put("lead_seconds",300)));
        assertEquals(300,TimerModel.lead(prefs,b));assertEquals(60,TimerModel.lead(prefs,boss("other","CHN 1")));
    }
    @Test public void muteIsScopedAndExpires()throws Exception {
        JSONObject prefs=new JSONObject().put("muted_until",new JSONObject().put("one",2000));
        assertTrue(TimerModel.muted(prefs,boss("one","CHN 1"),1000));assertFalse(TimerModel.muted(prefs,boss("two","CHN 1"),1000));assertFalse(TimerModel.muted(prefs,boss("one","CHN 1"),2001));
    }
    @Test public void nextEventTransitionsFromWarningToDeadline()throws Exception {
        JSONObject prefs=new JSONObject().put("lead_seconds",60),b=boss("default","CHN 1");b.put("end",2000);
        assertEquals(1940000,AlarmScheduler.nextTime(prefs,b,1000));
        b.put("warned_for",2000);assertEquals(2000000,AlarmScheduler.nextTime(prefs,b,1940));
        b.put("finished_for",2000);assertEquals(0,AlarmScheduler.nextTime(prefs,b,2001));
    }
    @Test public void zeroLeadAndOldDeadlinesDoNotReplayWarnings()throws Exception {
        JSONObject prefs=new JSONObject().put("lead_seconds",0),b=boss("default","CHN 1");b.put("end",2000);
        assertEquals(2000000,AlarmScheduler.nextTime(prefs,b,1000));assertEquals(0,AlarmScheduler.nextTime(prefs,b,3000));
        b.put("end",0);assertEquals(0,AlarmScheduler.nextTime(prefs,b,1000));
    }
    @Test public void newShortTimerWarnsOnceThenSchedulesDeadline()throws Exception {
        JSONObject b=boss("default","CHN 1");b.put("end",1060);
        JSONObject prefs=new JSONObject().put("lead_seconds",60);assertEquals(1001000,AlarmScheduler.nextTime(prefs,b,1000));
        b.put("warned_for",1060);assertEquals(1060000,AlarmScheduler.nextTime(prefs,b,1001));
    }
    @Test public void invalidBackupDoesNotPassValidation()throws Exception {
        JSONObject state=Store.empty();JSONObject b=boss("default","CHN 1");state.getJSONArray("bosses").put(b);TimerModel.validate(state);
        b.put("minutes",0);assertThrows(IllegalArgumentException.class,()->TimerModel.validate(state));
        b.put("minutes",180);state.getJSONArray("bosses").put(b);assertThrows(IllegalArgumentException.class,()->TimerModel.validate(state));
    }
}
