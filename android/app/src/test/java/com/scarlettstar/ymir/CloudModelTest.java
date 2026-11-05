package com.scarlettstar.ymir;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class CloudModelTest {
    JSONObject state()throws Exception {
        JSONObject s=Store.empty();s.getJSONObject("profiles").getJSONArray("profiles").getJSONObject(0).put("channel_view","CHN 1");
        JSONObject b=TimerModel.newBoss("Árvore",60,"Túmulo do Rei","CHN 1","Boss","default",true);b.put("id","boss-1").put("end",2000).put("last_kill",1000).put("warned_for",2000);s.getJSONArray("bosses").put(b);return s;
    }
    @Test public void roundTripKeepsDevicePreferencesAndWarnings()throws Exception {
        JSONObject s=state();s.getJSONObject("preferences").put("lead_seconds",180);
        JSONObject records=CloudModel.entities(s);assertFalse(records.toString().contains("warned_for"));assertFalse(records.toString().contains("channel_view"));
        assertTrue(CloudModel.equal(s,CloudModel.apply(s,records)));
    }
    @Test public void twoChannelsComposeWithoutMixingTimers()throws Exception {
        JSONObject s=state(),b=CloudModel.copy(s.getJSONArray("bosses").getJSONObject(0));b.put("id","boss-2").put("channel","CHN 2");s.getJSONArray("bosses").put(b);
        JSONObject local=CloudModel.copy(s),remote=CloudModel.copy(s);local.getJSONArray("bosses").getJSONObject(0).put("end",3000);remote.getJSONArray("bosses").getJSONObject(1).put("end",4000);
        CloudModel.Merged m=CloudModel.merge(CloudModel.entities(s),CloudModel.entities(local),CloudModel.entities(remote),false);JSONObject out=CloudModel.apply(s,m.records);
        assertEquals(0,m.conflicts.length());assertEquals(3000,out.getJSONArray("bosses").getJSONObject(0).getInt("end"));assertEquals(4000,out.getJSONArray("bosses").getJSONObject(1).getInt("end"));assertEquals(0,out.getJSONArray("bosses").getJSONObject(0).getInt("warned_for"));
    }
    @Test public void staleOfflineEditIsPreservedAsConflictNotUploadedOverNewTimer()throws Exception {
        JSONObject s=state(),local=CloudModel.copy(s),remote=CloudModel.copy(s);local.getJSONArray("bosses").getJSONObject(0).put("end",3000);remote.getJSONArray("bosses").getJSONObject(0).put("end",4000);
        CloudModel.Merged m=CloudModel.merge(CloudModel.entities(s),CloudModel.entities(local),CloudModel.entities(remote),false);
        assertEquals(4000,CloudModel.apply(s,m.records).getJSONArray("bosses").getJSONObject(0).getInt("end"));assertEquals(3000,m.conflicts.getJSONObject(0).getJSONObject("local").getInt("end"));
    }
    @Test public void remoteDeletionDoesNotResurrectOnUnchangedOfflineClient()throws Exception {
        JSONObject s=state(),base=CloudModel.entities(s),remote=CloudModel.copy(base);remote.remove("b:[\"default\",\"boss-1\"]");
        assertTrue(CloudModel.equal(remote,CloudModel.merge(base,base,remote,false).records));assertEquals(0,CloudModel.apply(s,remote).getJSONArray("bosses").length());
    }
    @Test public void inFlightLocalEditSurvivesForNextExchange()throws Exception {
        JSONObject s=state(),local=CloudModel.copy(s),remote=CloudModel.copy(s);local.getJSONArray("bosses").getJSONObject(0).put("end",5000);remote.getJSONArray("bosses").getJSONObject(0).put("end",4000);
        CloudModel.Merged m=CloudModel.merge(CloudModel.entities(s),CloudModel.entities(local),CloudModel.entities(remote),true);assertEquals(5000,CloudModel.apply(local,m.records).getJSONArray("bosses").getJSONObject(0).getInt("end"));
    }
    @Test public void crossPlatformIdentityUsesCompactUtf8AndMilliseconds()throws Exception {
        JSONObject s=state();s.getJSONArray("history").put(new JSONObject().put("name","Árvore").put("boss_id","boss-1").put("profile_id","default").put("category","Túmulo do Rei").put("killed_at",1000.125).put("respawn_at",2000));
        JSONObject e=CloudModel.entities(s);assertTrue(e.has("b:[\"default\",\"boss-1\"]"));assertTrue(e.has("h:[\"default\",\"boss-1\",1000125]"));
    }
}
