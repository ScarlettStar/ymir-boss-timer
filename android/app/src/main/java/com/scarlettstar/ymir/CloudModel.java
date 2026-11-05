package com.scarlettstar.ymir;

import org.json.*;
import java.util.*;

/** Same entity keys and three-way merge as ymir_cloud.py. Alert delivery is device-local. */
public final class CloudModel {
    private CloudModel() {}
    static JSONObject copy(JSONObject value) throws JSONException {return new JSONObject(value.toString());}
    static String canonical(Object value) throws JSONException {
        if(value instanceof JSONObject){JSONObject o=(JSONObject)value;List<String> keys=new ArrayList<>();o.keys().forEachRemaining(keys::add);Collections.sort(keys);List<String> parts=new ArrayList<>();for(String k:keys)parts.add(JSONObject.quote(k)+":"+canonical(o.get(k)));return "{"+String.join(",",parts)+"}";}
        if(value instanceof JSONArray){JSONArray a=(JSONArray)value;List<String> parts=new ArrayList<>();for(int i=0;i<a.length();i++)parts.add(canonical(a.get(i)));return "["+String.join(",",parts)+"]";}
        if(value instanceof Number)return new java.math.BigDecimal(value.toString()).stripTrailingZeros().toPlainString();
        if(value==null || value==JSONObject.NULL)return "null";
        return value instanceof String?JSONObject.quote((String)value):value.toString();
    }
    static boolean equal(Object a,Object b)throws JSONException {return canonical(a).equals(canonical(b));}
    public static JSONObject entities(JSONObject state)throws JSONException {
        JSONObject out=new JSONObject();JSONArray profiles=state.getJSONObject("profiles").getJSONArray("profiles");
        for(int i=0;i<profiles.length();i++){JSONObject p=copy(profiles.getJSONObject(i));p.remove("channel_view");out.put("p:"+p.getString("id"),p);}
        JSONArray bosses=state.getJSONArray("bosses");
        for(int i=0;i<bosses.length();i++){JSONObject b=copy(bosses.getJSONObject(i));b.remove("warned_for");b.remove("finished_for");out.put("b:"+canonical(new JSONArray().put(TimerModel.profile(b)).put(b.getString("id"))),b);}
        JSONArray history=state.getJSONArray("history");
        for(int i=0;i<history.length();i++){JSONObject h=history.getJSONObject(i);out.put("h:"+canonical(new JSONArray().put(TimerModel.profile(h)).put(h.optString("boss_id",h.getString("name"))).put((long)(h.getDouble("killed_at")*1000))),copy(h));}
        return out;
    }
    public static final class Merged {
        public final JSONObject records;public final JSONArray conflicts;
        Merged(JSONObject r,JSONArray c){records=r;conflicts=c;}
    }
    public static Merged merge(JSONObject base,JSONObject local,JSONObject remote,boolean preferLocal)throws JSONException {
        JSONObject out=copy(remote);JSONArray conflicts=new JSONArray();Set<String> keys=new TreeSet<>();base.keys().forEachRemaining(keys::add);local.keys().forEachRemaining(keys::add);
        for(String key:keys){Object old=base.opt(key),next=local.opt(key),other=remote.opt(key);if(equal(old,next))continue;
            if(!equal(other,old)&&!equal(other,next)){conflicts.put(new JSONObject().put("key",key).put("local",next==null?JSONObject.NULL:next));if(!preferLocal)continue;}
            if(next==null)out.remove(key);else out.put(key,next);
        }
        Set<String> ids=new HashSet<>();out.keys().forEachRemaining(k->{if(k.startsWith("p:"))ids.add(k.substring(2));});
        List<String> all=new ArrayList<>();out.keys().forEachRemaining(all::add);for(String k:all)if(!k.startsWith("p:")&&!ids.contains(TimerModel.profile(out.getJSONObject(k))))out.remove(k);
        collapseChannels(out,conflicts);
        return new Merged(out,conflicts);
    }
    static String normal(String text){return java.text.Normalizer.normalize(text.toLowerCase(java.util.Locale.ROOT),java.text.Normalizer.Form.NFKD).replaceAll("\\p{M}","").trim();}
    static String channelRegion(String region){String key=normal(region);if(key.startsWith("bosses "))key=key.substring(7).trim();if(key.equals("myrkheimr"))return "Bosses Myrkheimr";if(key.equals("tumulo do rei"))return "Túmulo do Rei";return "";}
    public static String channelKey(JSONObject boss)throws JSONException {
        String region=channelRegion(boss.optString("category")),channel=boss.optString("channel");if(region.isEmpty()||(!channel.equals("CHN 1")&&!channel.equals("CHN 2")))return "";
        return canonical(new JSONArray().put(TimerModel.profile(boss)).put(region).put(normal(boss.optString("name"))).put(normal(boss.optString("kind","Boss"))).put(channel));
    }
    static JSONArray cleanSamples(JSONArray samples)throws JSONException {
        java.util.Map<Double,JSONObject> valid=new java.util.TreeMap<>();
        if(samples!=null)for(int i=0;i<samples.length();i++){JSONObject pair=samples.optJSONObject(i);if(pair==null)continue;double kill=pair.optDouble("killed_at",0),spawn=pair.optDouble("spawned_at",0);if(!Double.isFinite(kill)||!Double.isFinite(spawn)||kill<=0||spawn<=kill||spawn-kill>604800)continue;if(!valid.containsKey(kill))valid.put(kill,new JSONObject().put("killed_at",kill).put("spawned_at",spawn));}
        JSONArray out=new JSONArray();int skip=Math.max(0,valid.size()-20),i=0;for(JSONObject pair:valid.values())if(i++>=skip)out.put(pair);return out;
    }
    static int compareChannelRows(JSONObject a,JSONObject b)throws JSONException {
        int n=Double.compare(a.optDouble("last_kill",0),b.optDouble("last_kill",0));if(n!=0)return n;
        n=Integer.compare(cleanSamples(a.optJSONArray("respawn_samples")).length(),cleanSamples(b.optJSONArray("respawn_samples")).length());if(n!=0)return n;
        n=Boolean.compare(a.optBoolean("favorite"),b.optBoolean("favorite"));return n!=0?n:a.getString("id").compareTo(b.getString("id"));
    }
    static void collapseChannels(JSONObject records,JSONArray conflicts)throws JSONException {
        java.util.Map<String,java.util.List<JSONObject>> groups=new java.util.LinkedHashMap<>();java.util.Iterator<String> keys=records.keys();while(keys.hasNext()){String k=keys.next();if(!k.startsWith("b:"))continue;JSONObject b=records.getJSONObject(k);String identity=channelKey(b);if(!identity.isEmpty())groups.computeIfAbsent(identity,unused->new java.util.ArrayList<>()).add(b);}
        for(java.util.List<JSONObject> rows:groups.values()){
            if(rows.size()<2)continue;JSONObject winner=rows.get(0);for(JSONObject row:rows)if(compareChannelRows(row,winner)>0)winner=row;
            java.util.List<JSONObject> pairs=new java.util.ArrayList<>();boolean favorite=false,myrk=false,tomb=false;
            for(JSONObject row:rows){JSONArray samples=cleanSamples(row.optJSONArray("respawn_samples"));for(int i=0;i<samples.length();i++)pairs.add(samples.getJSONObject(i));favorite|=row.optBoolean("favorite");myrk|=row.optBoolean("myrk_variable_v1");tomb|=row.optBoolean("tomb_channel_copy_v1");}
            pairs.sort((a,b)->{int n=Double.compare(b.optDouble("killed_at"),a.optDouble("killed_at"));return n!=0?n:Double.compare(b.optDouble("spawned_at"),a.optDouble("spawned_at"));});JSONArray all=new JSONArray();for(JSONObject pair:pairs)all.put(pair);winner.put("respawn_samples",cleanSamples(all));if(favorite)winner.put("favorite",true);if(myrk)winner.put("myrk_variable_v1",true);if(tomb)winner.put("tomb_channel_copy_v1",true);
            for(JSONObject row:rows)if(row!=winner){String key="b:"+canonical(new JSONArray().put(TimerModel.profile(row)).put(row.getString("id")));records.remove(key);conflicts.put(new JSONObject().put("key",key).put("local",row).put("reason","Mesmo boss na mesma conta, região e canal"));}
        }
    }
    public static void validatePairing(JSONObject base,JSONObject local,JSONObject remote)throws JSONException {
        java.util.Iterator<String> keys=local.keys();while(keys.hasNext()){
            String k=keys.next();if(!k.startsWith("p:")||base.has(k)||!remote.has(k))continue;
            JSONObject p=local.getJSONObject(k),other=remote.getJSONObject(k);
            if(!p.optString("server").trim().equalsIgnoreCase(other.optString("server").trim())){
                java.util.Iterator<String> all=local.keys();while(all.hasNext()){String b=all.next();if(b.startsWith("b:")&&TimerModel.profile(local.getJSONObject(b)).equals(p.getString("id")))throw new IllegalArgumentException("As contas locais e da nuvem usam o mesmo ID em servidores diferentes. Exporte um backup e importe o backup do PC no Android antes de conectar, ou use outro login para manter os conjuntos separados.");}
            }
        }
    }
    public static JSONObject apply(JSONObject state,JSONObject records)throws JSONException {
        if(records.length()>10000)throw new IllegalArgumentException("Estrutura de nuvem inválida.");
        java.util.Iterator<String> recordKeys=records.keys();while(recordKeys.hasNext()){
            String key=recordKeys.next();JSONObject v=records.getJSONObject(key);String expected;
            if(key.startsWith("p:"))expected="p:"+v.getString("id");
            else if(key.startsWith("b:"))expected="b:"+canonical(new JSONArray().put(TimerModel.profile(v)).put(v.getString("id")));
            else if(key.startsWith("h:"))expected="h:"+canonical(new JSONArray().put(TimerModel.profile(v)).put(v.optString("boss_id",v.getString("name"))).put((long)(v.getDouble("killed_at")*1000)));
            else throw new IllegalArgumentException("Registro desconhecido.");
            if(!key.equals(expected))throw new IllegalArgumentException("Identidade de nuvem inconsistente.");
        }
        JSONObject out=copy(state),profiles=out.getJSONObject("profiles");JSONArray accounts=new JSONArray(),bosses=new JSONArray();List<JSONObject> history=new ArrayList<>();
        List<String> keys=new ArrayList<>();records.keys().forEachRemaining(keys::add);Collections.sort(keys);Set<String> ids=new HashSet<>();
        JSONArray previous=state.getJSONObject("profiles").getJSONArray("profiles");
        for(String k:keys){JSONObject value=copy(records.getJSONObject(k));
            if(k.startsWith("p:")){ids.add(value.getString("id"));for(int i=0;i<previous.length();i++){JSONObject old=previous.getJSONObject(i);if(old.getString("id").equals(value.getString("id"))&&old.has("channel_view"))value.put("channel_view",old.get("channel_view"));}accounts.put(value);}
            else if(k.startsWith("b:")){JSONObject old=Store.find(state,TimerModel.profile(value),value.getString("id"));for(String field:new String[]{"warned_for","finished_for"})value.put(field,old!=null&&old.optDouble("end",0)==value.optDouble("end",0)?old.optDouble(field,0):0);bosses.put(value);}
            else if(k.startsWith("h:"))history.add(value);else throw new IllegalArgumentException("Registro de nuvem desconhecido.");
        }
        if(accounts.length()==0)throw new IllegalArgumentException("Nuvem sem contas.");
        profiles.put("profiles",accounts);if(!ids.contains(profiles.getString("active")))profiles.put("active",accounts.getJSONObject(0).getString("id"));
        history.sort(Comparator.comparingDouble(h->h.optDouble("killed_at",0)));JSONArray trimmed=new JSONArray();for(int i=Math.max(0,history.size()-1000);i<history.size();i++)trimmed.put(history.get(i));
        out.put("bosses",bosses).put("history",trimmed);TimerModel.validate(out);return out;
    }
}
