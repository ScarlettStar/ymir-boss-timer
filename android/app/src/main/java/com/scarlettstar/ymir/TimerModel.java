package com.scarlettstar.ymir;

import org.json.*;
import java.util.*;

/** Desktop-compatible seconds since epoch; observations are explicit death→spawn pairs. */
public final class TimerModel {
    public static final String[] REGIONS = {"Bosses Universais", "Bosses Myrkheimr", "Bosses Fólkvangr", "Túmulo do Rei"};
    private TimerModel() {}
    public static String profile(JSONObject boss) { return boss.optString("profile_id", "default"); }
    public static String key(JSONObject boss) { return "["+JSONObject.quote(profile(boss))+", "+JSONObject.quote(boss.optString("id"))+"]"; }
    public static String location(JSONObject boss) {
        return boss.optString("category", REGIONS[0]) +
            (boss.optString("channel").isEmpty() ? "" : " • " + boss.optString("channel")) +
            (boss.optString("floor").isEmpty() ? "" : " • " + boss.optString("floor"));
    }
    public static JSONObject newBoss(String name, int minutes, String region, String channel, String kind, String pid, boolean variable) throws JSONException {
        if (name.trim().isEmpty() || name.length() > 60 || minutes < 1 || minutes > 10080) throw new IllegalArgumentException("Informe nome e tempo de 1 a 10080 minutos.");
        return new JSONObject().put("id", UUID.randomUUID().toString()).put("profile_id", pid).put("name", name.trim())
            .put("minutes", minutes).put("category", region).put("channel", channel).put("floor", "")
            .put("kind", kind).put("variable_respawn", variable).put("myrk_variable_v1", true).put("tomb_channel_copy_v1", true)
            .put("respawn_samples", new JSONArray()).put("end", 0).put("last_kill", 0).put("spawn_for", 0).put("warned_for", 0).put("finished_for", 0);
    }
    public static double[] stats(JSONObject boss) throws JSONException {
        JSONArray samples = boss.optJSONArray("respawn_samples");
        double sum = 0, min = Double.MAX_VALUE, max = 0;
        int count = 0;
        if (samples != null) for (int i = Math.max(0, samples.length()-20); i < samples.length(); i++) {
            JSONObject pair = samples.getJSONObject(i);
            double duration = pair.getDouble("spawned_at")-pair.getDouble("killed_at");
            if (!Double.isFinite(duration) || duration <= 0 || duration > 604800) continue;
            sum += duration; min = Math.min(min, duration); max = Math.max(max, duration); count++;
        }
        return count == 0 ? new double[]{0, 0, 0, 0} : new double[]{count, sum/count, min, max};
    }
    public static double duration(JSONObject boss) throws JSONException {
        double[] stats = stats(boss);
        return boss.optBoolean("variable_respawn") && stats[0] > 0 ? stats[1] : boss.getInt("minutes")*60.0;
    }
    public static void kill(JSONObject boss, double now) throws JSONException {
        if (!Double.isFinite(now) || now <= 0) throw new IllegalArgumentException("Horário inválido.");
        boss.put("last_kill", now).put("end", now+duration(boss)).put("spawn_for", 0).put("warned_for", 0).put("finished_for", 0);
    }
    public static void observe(JSONObject boss, double now) throws JSONException {
        double killed = boss.optDouble("last_kill", 0);
        if (!boss.optBoolean("variable_respawn") || killed <= 0 || now <= killed || now-killed > 604800 || boss.optDouble("spawn_for", 0) == killed)
            throw new IllegalArgumentException("Confirme uma morte e registre um reaparecimento real, uma vez por ciclo.");
        JSONArray previous = boss.optJSONArray("respawn_samples"), next = new JSONArray();
        if (previous != null) for (int i = Math.max(0, previous.length()-19); i < previous.length(); i++) next.put(previous.getJSONObject(i));
        next.put(new JSONObject().put("killed_at", killed).put("spawned_at", now));
        boss.put("respawn_samples", next).put("spawn_for", killed).put("end", now).put("warned_for", now).put("finished_for", now);
    }
    public static int lead(JSONObject prefs, JSONObject boss) {
        JSONObject all = prefs.optJSONObject("boss_alerts");
        JSONObject options = all == null ? null : all.optJSONObject(key(boss));
        return Math.max(0, Math.min(3600, options == null ? prefs.optInt("lead_seconds", 60) : options.optInt("lead_seconds", prefs.optInt("lead_seconds", 60))));
    }
    public static boolean muted(JSONObject prefs, JSONObject boss, double now) {
        JSONObject muted = prefs.optJSONObject("muted_until");
        return muted != null && muted.optDouble(profile(boss), 0) > now;
    }
    public static List<JSONObject> visible(JSONArray bosses, String pid, String channel) throws JSONException {
        List<JSONObject> result = new ArrayList<>();
        for (int i=0;i<bosses.length();i++) {
            JSONObject b = bosses.getJSONObject(i);
            if (profile(b).equals(pid) && (channel.equals("Todos") || b.optString("channel").isEmpty() || channel.equals(b.optString("channel")))) result.add(b);
        }
        result.sort(Comparator.comparingDouble(b -> b.optDouble("end", 0) == 0 ? Double.MAX_VALUE : b.optDouble("end", 0)));
        return result;
    }
    public static void validate(JSONObject state) throws JSONException {
        JSONArray bosses = state.getJSONArray("bosses"), history = state.getJSONArray("history");
        JSONObject profiles = state.getJSONObject("profiles");
        JSONArray accounts = profiles.getJSONArray("profiles");
        Set<String> ids = new HashSet<>(), keys = new HashSet<>();
        if (accounts.length() == 0) throw new IllegalArgumentException("Backup sem contas.");
        for (int i=0;i<accounts.length();i++) {
            JSONObject p=accounts.getJSONObject(i);
            if (p.getString("id").isEmpty() || p.getString("name").trim().isEmpty() || !ids.add(p.getString("id"))) throw new IllegalArgumentException("Contas inválidas.");
            p.optString("server", "");
        }
        if (!ids.contains(profiles.getString("active"))) throw new IllegalArgumentException("Conta ativa inválida.");
        for (int i=0;i<bosses.length();i++) {
            JSONObject b=bosses.getJSONObject(i);
            if (b.getString("id").isEmpty() || b.getString("name").trim().isEmpty() || b.getString("name").length()>60 || !ids.contains(profile(b)) || !keys.add(key(b)) || b.getInt("minutes")<1 || b.getInt("minutes")>10080) throw new IllegalArgumentException("Boss inválido no backup.");
            for (String field:new String[]{"end","last_kill","spawn_for","warned_for","finished_for"}) {
                double time=b.optDouble(field,0);
                if (!Double.isFinite(time) || time<0 || time>4102444800.0) throw new IllegalArgumentException("Horário inválido.");
            }
            stats(b);
        }
        for(int i=0;i<history.length();i++) {
            JSONObject h=history.getJSONObject(i);
            if(!ids.contains(profile(h)) || !Double.isFinite(h.getDouble("killed_at")) || !Double.isFinite(h.getDouble("respawn_at"))) throw new IllegalArgumentException("Histórico inválido.");
            h.getString("name"); h.getString("category");
        }
        state.getJSONObject("preferences");
    }
}
