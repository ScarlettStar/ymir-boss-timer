package com.scarlettstar.ymir;

import org.json.*;

/** Read-only status; silence is not proof that the game/PC stopped. */
public final class HuntLiveModel {
    private HuntLiveModel() {}
    public static boolean fresh(double received,double now){return Double.isFinite(received)&&received>0&&now-received>=-60&&now-received<=90;}
    public static JSONObject validate(JSONObject value)throws JSONException {
        if(value.optInt("schema")!=1||value.toString().length()>60000||value.optString("profile_id").isEmpty()||value.optString("device_id").isEmpty())throw new IllegalArgumentException("Estado de caça inválido.");
        for(String key:new String[]{"running","paused","simulate"})if(!(value.get(key) instanceof Boolean))throw new IllegalArgumentException("Estado de caça inválido.");
        for(String key:new String[]{"boss","map","stage","next_visit","device_label"})if(!(value.opt(key) instanceof String)||value.getString(key).length()>500)throw new IllegalArgumentException("Texto de caça inválido.");
        return value;
    }
    public static String eventLabel(String value){
        switch(value){
            case "combate_encerrado":case "combate_encerrado_no_farm":return "Morte estimada";
            case "combate_inconclusivo":return "Combate inconclusivo";
            case "boss_visto":return "Boss encontrado";
            case "ausente":return "Boss ausente";
            case "morte_registrada":return "Morte registrada";
            case "timer_sincronizado":return "Timer sincronizado";
            case "timer_limpo":return "Timer limpo manualmente";
            default:return value.replace('_',' ');
        }
    }
    public static String badge(JSONObject value,double now){
        if(!fresh(value.optDouble("received_at",0),now))return "SEM ATUALIZAÇÃO RECENTE";
        if(value.optBoolean("simulate"))return "SIMULAÇÃO";
        if(value.optBoolean("paused"))return "PAUSADO";
        return value.optBoolean("running")?"EM EXECUÇÃO":"PARADO";
    }
}
