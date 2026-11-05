package com.scarlettstar.ymir;
import org.json.*;
import java.util.*;
import org.junit.Test;
import static org.junit.Assert.*;

public class CatalogLayoutTest {
    JSONObject boss(String name,String region,String floor,String channel,int end)throws Exception {
        return new JSONObject().put("id",UUID.randomUUID().toString()).put("profile_id","default").put("name",name).put("category",region).put("floor",floor).put("channel",channel).put("end",end);
    }
    @Test public void regionsAndFloorsKeepRequestedRoleOrderWithoutChangingTimers()throws Exception {
        List<JSONObject> rows=new ArrayList<>();for(String f:new String[]{"P2","P1"})for(String role:new String[]{"Escald","Maga","Guerreiro","Lanceiro"})rows.add(boss(role,TimerModel.REGIONS[2],f,"",rows.size()*100));
        rows.get(0).put("favorite",true);List<String> original=new ArrayList<>();for(JSONObject b:rows)original.add(b.toString());
        List<JSONObject> ordered=CatalogLayout.ordered(rows);
        for(int i=0;i<ordered.size();i++){assertEquals(i<4?"P1":"P2",ordered.get(i).getString("floor"));assertEquals(new String[]{"Guerreiro","Lanceiro","Maga","Escald"}[i%4],ordered.get(i).getString("name"));}
        for(int i=0;i<rows.size();i++)assertEquals(original.get(i),rows.get(i).toString());
    }
    @Test public void channelRegionsAndCustomRegionsAreContiguousWithStableInternalChronology()throws Exception {
        List<JSONObject> rows=Arrays.asList(boss("Custom","Labirinto Albit","","",10),boss("Myrk 2",TimerModel.REGIONS[1],"","CHN 2",20),boss("Myrk 1",TimerModel.REGIONS[1],"","CHN 1",30),boss("Túmulo",TimerModel.REGIONS[3],"","CHN 2",40),boss("Segundo","Labirinto Albit","","",50));
        List<JSONObject> ordered=CatalogLayout.ordered(rows);assertEquals("Myrk 1",ordered.get(0).getString("name"));assertEquals("Myrk 2",ordered.get(1).getString("name"));assertEquals("Túmulo",ordered.get(2).getString("name"));assertEquals("Custom",ordered.get(3).getString("name"));assertEquals("Segundo",ordered.get(4).getString("name"));
        assertEquals("CHN 2",CatalogLayout.section(ordered.get(1)));assertEquals("",CatalogLayout.section(ordered.get(3)));
    }
}
