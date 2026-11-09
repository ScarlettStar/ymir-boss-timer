package com.scarlettstar.ymir;

import org.json.*;
import java.util.*;

/** Presentation only: grouping and ordering never change records or alert scheduling. */
public final class CatalogLayout {
    private static final List<String> ROLES=Arrays.asList("guerreiro","lanceiro","maga","escald");
    private static final List<String> FLOORS=Arrays.asList("P1","P2","P3","P4 UNIVERSAL");
    private CatalogLayout() {}
    public static String region(JSONObject boss) {
        String raw=boss.optString("category",TimerModel.REGIONS[0]).trim();
        String channels=CloudModel.channelRegion(raw);if(!channels.isEmpty())return channels;
        String normal=CloudModel.normal(raw);if(normal.equals("folk")||normal.equals("folkvangr")||normal.equals("bosses folkvangr"))return TimerModel.REGIONS[2];
        return raw.isEmpty()?TimerModel.REGIONS[0]:raw;
    }
    public static String section(JSONObject boss) {
        String region=region(boss);
        if(region.equals(TimerModel.REGIONS[2]))return boss.optString("floor").isEmpty()?"Sem piso":boss.optString("floor");
        String channel=TimerModel.channelLabel(boss);
        if(!channel.isEmpty())return channel;
        if(!CloudModel.channelRegion(region).isEmpty())return "Sem canal";
        return boss.optString("floor");
    }
    private static int regionRank(String region){int i=Arrays.asList(TimerModel.REGIONS).indexOf(region);return i<0?TimerModel.REGIONS.length:i;}
    private static int sectionRank(JSONObject b) {
        if(region(b).equals(TimerModel.REGIONS[2])){int i=FLOORS.indexOf(section(b));return i<0?FLOORS.size():i;}
        int channel=TimerModel.channelNumber(b);return channel==0?4:channel;
    }
    private static int roleRank(JSONObject b){int i=ROLES.indexOf(CloudModel.normal(b.optString("name")));return i<0?ROLES.size():i;}
    public static List<JSONObject> ordered(List<JSONObject> bosses) {
        List<JSONObject> out=new ArrayList<>(bosses);
        out.sort((a,b)->{
            int n=Integer.compare(regionRank(region(a)),regionRank(region(b)));if(n!=0)return n;
            n=CloudModel.normal(region(a)).compareTo(CloudModel.normal(region(b)));if(n!=0)return n;
            n=Integer.compare(sectionRank(a),sectionRank(b));if(n!=0)return n;
            n=section(a).compareTo(section(b));if(n!=0)return n;
            if(region(a).equals(TimerModel.REGIONS[2])){
                n=Integer.compare(roleRank(a),roleRank(b));if(n!=0)return n;
                return CloudModel.normal(a.optString("name")).compareTo(CloudModel.normal(b.optString("name")));
            }
            return CloudModel.normal(a.optString("name")).compareTo(CloudModel.normal(b.optString("name")));
        });return out;
    }
}

