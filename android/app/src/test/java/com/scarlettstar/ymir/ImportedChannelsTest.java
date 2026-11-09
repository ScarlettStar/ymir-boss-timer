package com.scarlettstar.ymir;
import org.json.*;
import org.junit.Test;
import java.util.*;
import static org.junit.Assert.*;

public class ImportedChannelsTest {
    private JSONObject boss(String name,int channel,String pid)throws Exception{return TimerModel.newBoss(name,10,"Vale de Ragnarök","","Boss",pid,false).put("hunt_channel",channel);}
    @Test public void importedChannelsFilterWithoutChangingAnyTimerOrCreatingCopies()throws Exception {
        JSONObject one=boss("Um",1,"default"),two=boss("Dois",2,"default"),three=boss("Três",3,"default"),other=boss("Outra conta",1,"other");
        JSONArray all=new JSONArray().put(one).put(two).put(three).put(other);String original=all.toString();
        for(int c=1;c<=3;c++){List<JSONObject> rows=TimerModel.visible(all,"default","CHN "+c);assertEquals(1,rows.size());assertEquals(c,TimerModel.channelNumber(rows.get(0)));}
        assertEquals(3,TimerModel.visible(all,"default","Todos").size());assertEquals(original,all.toString());
        assertEquals(Arrays.asList("Todos","CHN 1","CHN 2","CHN 3"),TimerModel.channelChoices(all,"default"));
        assertEquals(Arrays.asList("Todos","CHN 1","CHN 2"),TimerModel.channelChoices(all,"other"));
    }
    @Test public void channelResolutionUsesExplicitFieldsAndNeverBossName()throws Exception {
        JSONObject b=boss("Nome com canal 3",0,"default");assertEquals(0,TimerModel.channelNumber(b));
        b.put("hunt_auto_key","mapa|Nome|2");assertEquals(2,TimerModel.channelNumber(b));
        b.put("hunt_channel",1);assertEquals(1,TimerModel.channelNumber(b));
        b.put("channel","Canal 3");assertEquals(3,TimerModel.channelNumber(b));assertTrue(TimerModel.location(b).contains("CHN 3"));
        b.put("channel","CHN 20").remove("hunt_auto_key");b.remove("hunt_channel");assertEquals(0,TimerModel.channelNumber(b));
        b.put("hunt_channel",1.5);assertEquals(0,TimerModel.channelNumber(b));
    }
    @Test public void allMapsGroupByChannelThenNameAndKeepFolkvangrRoleOrder()throws Exception {
        List<JSONObject> rows=Arrays.asList(boss("Zeta",2,"default"),boss("Zulu",1,"default"),boss("Alpha",1,"default"),boss("Terceiro",3,"default"));
        List<JSONObject> ordered=CatalogLayout.ordered(rows);
        assertEquals("Alpha",ordered.get(0).getString("name"));assertEquals("Zulu",ordered.get(1).getString("name"));
        assertEquals("CHN 2",CatalogLayout.section(ordered.get(2)));assertEquals("CHN 3",CatalogLayout.section(ordered.get(3)));
        assertEquals("Zeta",rows.get(0).getString("name"));
    }
    @Test public void automaticDeathAlreadyHasCountdownAndIsNeverReplacedByArrivalTime()throws Exception {
        JSONObject state=Store.empty(),b=boss("Recebido",2,"default");state.getJSONArray("bosses").put(b);
        JSONObject remote=new JSONObject(state.toString()),received=remote.getJSONArray("bosses").getJSONObject(0);
        received.put("last_kill",2000).put("end",2600).put("kill_source","auto_estimated").put("hunt_event_id","event-one");
        remote.getJSONArray("history").put(new JSONObject().put("profile_id","default").put("boss_id",b.getString("id")).put("name","Recebido").put("category","Vale de Ragnarök").put("killed_at",2000).put("respawn_at",2600));
        JSONObject applied=CloudModel.apply(state,CloudModel.entities(remote));
        JSONObject twice=CloudModel.apply(applied,CloudModel.entities(remote)),timer=twice.getJSONArray("bosses").getJSONObject(0);
        assertEquals("MATEI AUTOMÁTICO • morte estimada",TimerModel.deathLabel(timer));
        assertEquals(2000,timer.getDouble("last_kill"),0);assertEquals(2600,timer.getDouble("end"),0);assertEquals(1,twice.getJSONArray("history").length());
        assertEquals("event-one",timer.getString("hunt_event_id"));
    }
    @Test public void resetAndUnstartedTimersDoNotLookAutomaticallyKilled()throws Exception {
        JSONObject b=boss("Sem morte",1,"default");assertEquals("",TimerModel.deathLabel(b));
        b.put("last_kill",1000).put("end",0).put("kill_source","auto_estimated");assertEquals("",TimerModel.deathLabel(b));
        TimerModel.kill(b,2000);assertEquals("MATEI • registro manual",TimerModel.deathLabel(b));
    }
}
