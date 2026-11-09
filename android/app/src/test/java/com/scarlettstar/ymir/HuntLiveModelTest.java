package com.scarlettstar.ymir;
import org.json.*;
import org.junit.Test;
import static org.junit.Assert.*;
public class HuntLiveModelTest {
    JSONObject live()throws Exception{return new JSONObject().put("schema",1).put("device_id","a").put("profile_id","default").put("running",true).put("paused",false).put("simulate",false).put("boss","Boss").put("map","Mapa").put("stage","Combate").put("next_visit","Outro").put("device_label","PC").put("received_at",100);}
    @Test public void staleDoesNotClaimRunning()throws Exception{JSONObject value=live();assertEquals("EM EXECUÇÃO",HuntLiveModel.badge(value,120));assertEquals("SEM ATUALIZAÇÃO RECENTE",HuntLiveModel.badge(value,191));}
    @Test public void pausedSimulationAndStoppedAreExplicit()throws Exception{JSONObject value=live();value.put("paused",true);assertEquals("PAUSADO",HuntLiveModel.badge(value,120));value.put("simulate",true);assertEquals("SIMULAÇÃO",HuntLiveModel.badge(value,120));value.put("paused",false).put("simulate",false).put("running",false);assertEquals("PARADO",HuntLiveModel.badge(value,120));}
    @Test public void invalidStateCannotBecomeLive()throws Exception{JSONObject value=live();value.put("running","true");try{HuntLiveModel.validate(value);fail();}catch(IllegalArgumentException expected){}}
}
