package com.scarlettstar.ymir;

import android.Manifest;
import android.app.*;
import android.content.*;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.*;
import android.provider.Settings;
import android.text.*;
import android.view.*;
import android.widget.*;
import org.json.*;
import java.io.*;
import java.text.SimpleDateFormat;
import java.util.*;

public final class MainActivity extends Activity {
    private static final int BG=0xff0b101d, PANEL=0xff172238, TEXT=0xffe8eefb, MUTED=0xff9aabc7, ACCENT=0xff5ae2c0, PURPLE=0xffb99aff, WARNING=0xffffd080;
    private Store store;
    private JSONObject state;
    private LinearLayout root, body, accountsBar;
    private String tab="Bosses", channel="Todos", query="";
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final Map<TextView,JSONObject> timers=new LinkedHashMap<>();
    private boolean healthy=true;
    private final Runnable clock=new Runnable() {
        @Override public void run() {
            double now=System.currentTimeMillis()/1000.0;
            for(Map.Entry<TextView,JSONObject> entry:timers.entrySet())entry.getKey().setText(countdown(entry.getValue(),now));
            handler.postDelayed(this,1000);
        }
    };
    private int dp(int n) { return Math.round(n*getResources().getDisplayMetrics().density); }
    private TextView label(String text,int size,int color) {
        TextView view=new TextView(this);view.setText(text);view.setTextSize(size);view.setTextColor(color);view.setPadding(0,dp(4),0,dp(4));return view;
    }
    private LinearLayout column() { LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);return v; }
    private LinearLayout row() { LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.HORIZONTAL);return v; }
    private GradientDrawable surface(int color) { GradientDrawable d=new GradientDrawable();d.setColor(color);d.setCornerRadius(dp(15));d.setStroke(dp(1),0xff2a3a54);return d; }
    private Button button(String text,Runnable action) {
        Button b=new Button(this);b.setText(text);b.setTextColor(ACCENT);b.setAllCaps(false);b.setTextSize(13);b.setMinHeight(dp(44));b.setBackgroundTintList(android.content.res.ColorStateList.valueOf(PANEL));b.setOnClickListener(v->action.run());return b;
    }
    private void addButton(LinearLayout parent,String text,Runnable action) { parent.addView(button(text,action),new LinearLayout.LayoutParams(-1,-2)); }
    private void rowButton(LinearLayout parent,String text,Runnable action) { LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,1);p.setMargins(dp(2),0,dp(2),0);parent.addView(button(text,action),p); }
    private void error(Exception e) { new AlertDialog.Builder(this).setTitle("Não foi possível concluir").setMessage(e.getMessage()==null?e.toString():e.getMessage()).setPositiveButton("OK",null).show(); }
    private void message(String text) { Toast.makeText(this,text,Toast.LENGTH_LONG).show(); }
    private String pid() { return state.optJSONObject("profiles").optString("active","default"); }
    private JSONObject account(JSONObject s,String id) throws JSONException {
        JSONArray profiles=s.getJSONObject("profiles").getJSONArray("profiles");
        for(int i=0;i<profiles.length();i++)if(profiles.getJSONObject(i).getString("id").equals(id))return profiles.getJSONObject(i);
        throw new IllegalArgumentException("Conta não encontrada.");
    }
    @Override public void onCreate(Bundle saved) {
        super.onCreate(saved);
        store=new Store(this);
        try { state=store.read(); } catch(Exception e) { healthy=false;state=new JSONObject();new AlertDialog.Builder(this).setTitle("Dados não carregados").setMessage("Os dados foram preservados. Não será criado um cadastro vazio por cima deles.\n"+e.getMessage()).setPositiveButton("Fechar",(d,w)->finish()).show();return; }
        root=column();root.setBackgroundColor(BG);root.setPadding(dp(14),dp(12),dp(14),0);setContentView(root);
        if(Build.VERSION.SDK_INT>=30)root.setOnApplyWindowInsetsListener((v,insets)->{android.graphics.Insets sys=insets.getInsets(WindowInsets.Type.systemBars());v.setPadding(dp(14)+sys.left,dp(8)+sys.top,dp(14)+sys.right,sys.bottom);return insets;});
        // Insets API 30 is guarded separately for Android 8–10.
        else root.setFitsSystemWindows(true);
        TextView title=label("⚔  YMIR",28,ACCENT);title.setTypeface(null,Typeface.BOLD);root.addView(title);
        root.addView(label("BOSS TIMER  •  ANDROID PREVIEW",11,MUTED));
        accountsBar=column();root.addView(accountsBar);
        LinearLayout navigation=row();for(String name:new String[]{"Bosses","Próximos","Contas","Ajustes"})rowButton(navigation,name,()->{tab=name;render();});root.addView(navigation);
        ScrollView scroll=new ScrollView(this);body=column();scroll.addView(body);root.addView(scroll,new LinearLayout.LayoutParams(-1,0,1));
        AlarmReceiver.channels(this);
        render();
    }
    @Override public void onResume() {
        super.onResume();if(!healthy)return;
        try { state=store.read();AlarmScheduler.reschedule(this,state);if(root!=null)render(); }catch(Exception e){error(e);}
        handler.removeCallbacks(clock);handler.post(clock);
    }
    @Override public void onPause() { handler.removeCallbacks(clock);super.onPause(); }
    private void save(JSONObject next) throws Exception { store.write(next);state=next;AlarmScheduler.reschedule(this,next);render(); }
    private void render() {
        if(body==null)return;
        try {
            state=store.read();
            channel=account(state,pid()).optString("channel_view","Todos");
            if(!Arrays.asList("Todos","CHN 1","CHN 2").contains(channel))channel="Todos";
            timers.clear();accountsBar.removeAllViews();body.removeAllViews();
            JSONArray profiles=state.getJSONObject("profiles").getJSONArray("profiles");List<String> labels=new ArrayList<>();int active=0;
            for(int i=0;i<profiles.length();i++) { JSONObject p=profiles.getJSONObject(i);labels.add(p.getString("name")+" / "+p.optString("server","sem servidor"));if(p.getString("id").equals(pid()))active=i; }
            Spinner selector=spinner(labels);selector.setSelection(active);accountsBar.addView(selector);
            selector.setOnItemSelectedListener(new SimpleSelection(){@Override public void selected(int i){try {String id=profiles.getJSONObject(i).getString("id");if(!id.equals(pid())){JSONObject next=store.read();next.getJSONObject("profiles").put("active",id);query="";save(next);}}catch(Exception e){error(e);}}});
            if(tab.equals("Contas")){renderAccounts();return;}if(tab.equals("Ajustes")){renderSettings();return;}
            LinearLayout channels=row();for(String c:new String[]{"Todos","CHN 1","CHN 2"})rowButton(channels,(channel.equals(c)?"● ":"")+c,()->{try{JSONObject next=store.read();account(next,pid()).put("channel_view",c);save(next);}catch(Exception e){error(e);}});body.addView(channels);
            if(tab.equals("Bosses")) {
                addButton(body,"+ Cadastrar boss",this::bossDialog);
                EditText search=input("Buscar boss, região ou canal",query,false);body.addView(search);
                LinearLayout cards=column();body.addView(cards);
                drawCards(cards);
                search.addTextChangedListener(new TextWatcher(){public void beforeTextChanged(CharSequence s,int st,int count,int after){}public void onTextChanged(CharSequence s,int st,int before,int count){query=s.toString();try{timers.clear();cards.removeAllViews();drawCards(cards);}catch(Exception e){error(e);}}public void afterTextChanged(Editable e){}});
            } else drawCards(body);
        }catch(Exception e){error(e);}
    }
    private void drawCards(LinearLayout container) throws Exception {
        List<JSONObject> bosses=TimerModel.visible(state.getJSONArray("bosses"),pid(),channel);int shown=0;
        for(JSONObject b:bosses) {
            if(tab.equals("Próximos") && b.optDouble("end",0)==0)continue;
            if(!(b.getString("name")+" "+TimerModel.location(b)).toLowerCase(Locale.ROOT).contains(query.toLowerCase(Locale.ROOT)))continue;
            shown++;
            LinearLayout card=column();card.setPadding(dp(14),dp(10),dp(14),dp(12));card.setBackground(surface(PANEL));
            LinearLayout.LayoutParams layout=new LinearLayout.LayoutParams(-1,-2);layout.setMargins(0,dp(8),0,dp(4));container.addView(card,layout);
            card.addView(label(TimerModel.location(b)+" • "+b.optString("kind","Boss"),11,PURPLE));
            TextView name=label(b.getString("name"),21,TEXT);name.setTypeface(null,Typeface.BOLD);card.addView(name);
            TextView time=label(countdown(b,System.currentTimeMillis()/1000.0),28,ACCENT);time.setTypeface(Typeface.MONOSPACE,Typeface.BOLD);card.addView(time);timers.put(time,b);
            if(b.optDouble("end",0)>0)card.addView(label((b.optBoolean("variable_respawn")?"Previsão: ":"Horário: ")+new SimpleDateFormat("dd/MM HH:mm:ss",Locale.getDefault()).format(new Date((long)(b.optDouble("end")*1000))),13,MUTED));
            if(b.optBoolean("variable_respawn")) {
                double[] stats=TimerModel.stats(b);
                card.addView(label(stats[0]==0?"Variável • sem observações; referência "+b.optInt("minutes")+" min":String.format(Locale.getDefault(),"Média %.1f min • mín./máx. %.1f–%.1f • %d registros\nEstimativa; confirme no jogo.",stats[1]/60,stats[2]/60,stats[3]/60,(int)stats[0]),12,WARNING));
            }
            LinearLayout actions=row();rowButton(actions,"Matei",()->kill(b));if(b.optBoolean("variable_respawn"))rowButton(actions,"Reapareceu",()->observe(b));rowButton(actions,"Opções",()->bossOptions(b));card.addView(actions);
        }
        if(shown==0)container.addView(label("Nenhum boss nesta visualização. Cadastre um boss ou importe seu backup do PC em Ajustes.",16,MUTED));
    }
    private String countdown(JSONObject b,double now) {
        double end=b.optDouble("end",0);if(end<=0)return "SEM CONTAGEM";
        long remain=(long)Math.ceil(end-now);if(remain<=0)return b.optBoolean("variable_respawn")?"PREVISTO • CONFIRA":"HORÁRIO DO RESPAWN";
        return (b.optBoolean("variable_respawn")?"~":"")+String.format(Locale.ROOT,"%02d:%02d:%02d",remain/3600,remain%3600/60,remain%60);
    }
    @FunctionalInterface private interface BossEdit {void change(JSONObject next,JSONObject boss)throws Exception;}
    private void edit(JSONObject old,BossEdit change) {
        try {JSONObject next=store.read();JSONObject boss=Store.find(next,TimerModel.profile(old),old.getString("id"));if(boss==null)throw new IllegalArgumentException("Boss removido.");change.change(next,boss);save(next);}catch(Exception e){error(e);}
    }
    private void kill(JSONObject old) {
        new AlertDialog.Builder(this).setTitle("Registrar morte?").setMessage(old.optString("name")+"\n"+TimerModel.location(old)+"\nA contagem deste boss será reiniciada.").setNegativeButton("Cancelar",null).setPositiveButton("Matei agora",(d,w)->edit(old,(next,b)->{
            double now=System.currentTimeMillis()/1000.0;TimerModel.kill(b,now);
            JSONArray history=next.getJSONArray("history");
            history.put(new JSONObject().put("name",b.getString("name")).put("category",b.getString("category")).put("kind",b.optString("kind","Boss")).put("channel",b.optString("channel","")).put("floor",b.optString("floor","")).put("boss_id",b.getString("id")).put("profile_id",TimerModel.profile(b)).put("variable_respawn",b.optBoolean("variable_respawn")).put("killed_at",now).put("respawn_at",b.getDouble("end")));
            if(history.length()>2000){JSONArray trimmed=new JSONArray();for(int i=history.length()-2000;i<history.length();i++)trimmed.put(history.getJSONObject(i));next.put("history",trimmed);}
        })).show();
    }
    private void observe(JSONObject old) {
        new AlertDialog.Builder(this).setTitle("Boss reapareceu agora?").setMessage("Use somente quando observar o nascimento real. Isso alimenta a média deste boss, conta e canal.").setNegativeButton("Cancelar",null).setPositiveButton("Reapareceu",(d,w)->edit(old,(next,b)->{
            double now=System.currentTimeMillis()/1000.0;TimerModel.observe(b,now);
            JSONArray history=next.getJSONArray("history");for(int i=history.length()-1;i>=0;i--){JSONObject h=history.getJSONObject(i);if(h.optString("boss_id").equals(b.getString("id"))&&TimerModel.profile(h).equals(TimerModel.profile(b))&&h.optDouble("killed_at")==b.getDouble("last_kill")){h.put("observed_respawn_at",now);break;}}
        })).show();
    }
    private void bossOptions(JSONObject old) {
        new AlertDialog.Builder(this).setTitle(old.optString("name")).setItems(new String[]{"Zerar contagem","Editar minutos","Alternar fixo / variável","Remover boss"},(d,index)->{
            if(index==1){EditText minutes=input("Minutos",String.valueOf(old.optInt("minutes")),true);new AlertDialog.Builder(this).setTitle("Tempo de referência").setView(minutes).setNegativeButton("Cancelar",null).setPositiveButton("Salvar",(x,w)->edit(old,(next,b)->{int n=Integer.parseInt(minutes.getText().toString());if(n<1||n>10080)throw new IllegalArgumentException("Use de 1 a 10080 minutos.");b.put("minutes",n);if(b.optDouble("end",0)>System.currentTimeMillis()/1000.0)b.put("end",b.getDouble("last_kill")+TimerModel.duration(b)).put("warned_for",0).put("finished_for",0);})).show();return;}
            if(index==3){new AlertDialog.Builder(this).setTitle("Remover este boss?").setMessage("Apenas esta conta e canal serão alterados.").setNegativeButton("Cancelar",null).setPositiveButton("Remover",(x,w)->edit(old,(next,b)->{JSONArray all=next.getJSONArray("bosses");for(int i=0;i<all.length();i++)if(TimerModel.key(all.getJSONObject(i)).equals(TimerModel.key(b))){all.remove(i);break;}})).show();return;}
            edit(old,(next,b)->{if(index==0)b.put("end",0).put("last_kill",0).put("spawn_for",0).put("warned_for",0).put("finished_for",0);else {b.put("variable_respawn",!b.optBoolean("variable_respawn"));if(b.optDouble("end",0)>System.currentTimeMillis()/1000.0)b.put("end",b.getDouble("last_kill")+TimerModel.duration(b)).put("warned_for",0).put("finished_for",0);}});
        }).show();
    }
    private EditText input(String hint,String value,boolean number) { EditText e=new EditText(this);e.setHint(hint);e.setText(value);e.setTextColor(TEXT);e.setHintTextColor(MUTED);e.setTextSize(15);e.setSingleLine(true);e.setInputType(number?android.text.InputType.TYPE_CLASS_NUMBER:android.text.InputType.TYPE_CLASS_TEXT);return e; }
    private Spinner spinner(List<String> values) {Spinner spinner=new Spinner(this);spinner.setAdapter(new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,values));return spinner;}
    private abstract static class SimpleSelection implements AdapterView.OnItemSelectedListener {abstract void selected(int i);public void onItemSelected(AdapterView<?> p,View v,int i,long id){selected(i);}public void onNothingSelected(AdapterView<?> p){}}
    private void bossDialog() {
        LinearLayout fields=column();fields.setPadding(dp(18),0,dp(18),0);
        EditText name=input("Nome do boss","",false),minutes=input("Respawn em minutos","180",true),region=input("Região (pode criar outra)",TimerModel.REGIONS[0],false),kind=input("Categoria","Boss",false);
        Spinner presets=spinner(Arrays.asList(TimerModel.REGIONS)),place=spinner(Arrays.asList("Sem canal/piso","CHN 1","CHN 2","P1","P2","P3","P4 UNIVERSAL"));
        CheckBox variable=new CheckBox(this);variable.setText("Respawn variável (aprender média)");variable.setTextColor(TEXT);
        for(View v:new View[]{name,minutes,presets,region,kind,place,variable})fields.addView(v);
        presets.setOnItemSelectedListener(new SimpleSelection(){void selected(int i){region.setText(TimerModel.REGIONS[i]);variable.setChecked(i==1);}});
        new AlertDialog.Builder(this).setTitle("Cadastrar boss • "+accountName()).setView(fields).setNegativeButton("Cancelar",null).setPositiveButton("Adicionar",(d,w)->{
            try{JSONObject next=store.read();String category=region.getText().toString().trim(),type=kind.getText().toString().trim();if(category.isEmpty()||category.length()>60||type.isEmpty()||type.length()>60)throw new IllegalArgumentException("Informe região e categoria de até 60 caracteres.");String location=place.getSelectedItem().toString();JSONObject b=TimerModel.newBoss(name.getText().toString(),Integer.parseInt(minutes.getText().toString()),category,location.startsWith("CHN")?location:"",type,pid(),variable.isChecked());if(location.startsWith("P"))b.put("floor",location);next.getJSONArray("bosses").put(b);save(next);}catch(Exception e){error(e);}
        }).show();
    }
    private String accountName() {try{return account(state,pid()).getString("name");}catch(Exception e){return "Conta";}}
    private void renderAccounts() throws Exception {
        addButton(body,"+ Adicionar conta / servidor",()->{
            LinearLayout fields=column();EditText name=input("Nome da conta","",false),server=input("Servidor (ex.: SA012)","",false);fields.addView(name);fields.addView(server);
            new AlertDialog.Builder(this).setTitle("Nova conta independente").setView(fields).setNegativeButton("Cancelar",null).setPositiveButton("Criar",(d,w)->{
                try{String n=name.getText().toString().trim(),s=server.getText().toString().trim();if(n.isEmpty()||s.isEmpty()||n.length()>60||s.length()>60)throw new IllegalArgumentException("Informe nome e servidor (até 60 caracteres).");JSONObject next=store.read();JSONArray all=next.getJSONObject("profiles").getJSONArray("profiles");for(int i=0;i<all.length();i++)if(all.getJSONObject(i).getString("name").equalsIgnoreCase(n)&&all.getJSONObject(i).optString("server").equalsIgnoreCase(s))throw new IllegalArgumentException("Conta já cadastrada.");String id=UUID.randomUUID().toString();all.put(new JSONObject().put("id",id).put("name",n).put("server",s).put("regions",new JSONArray()));next.getJSONObject("profiles").put("active",id);save(next);}catch(Exception e){error(e);}
            }).show();
        });
        JSONArray profiles=state.getJSONObject("profiles").getJSONArray("profiles");double now=System.currentTimeMillis()/1000.0;
        for(int i=0;i<profiles.length();i++){JSONObject p=profiles.getJSONObject(i);int active=0,ready=0;for(JSONObject b:TimerModel.visible(state.getJSONArray("bosses"),p.getString("id"),"Todos")){double end=b.optDouble("end",0);if(end>now)active++;else if(end>0)ready++;}body.addView(label(p.getString("name")+" / "+p.optString("server","")+"\n"+active+" timers ativos • "+ready+" prontos/previstos",17,TEXT));}
        body.addView(label("As contas são locais deste celular. Esta prévia ainda não sincroniza automaticamente com o PC.",14,WARNING));
    }
    private void renderSettings() throws Exception {
        body.addView(label("ALERTAS NO CELULAR",18,ACCENT));
        body.addView(label((AlarmReceiver.notificationsEnabled(this)?"✓ Notificações permitidas":"⚠ Notificações bloqueadas")+"\n"+(AlarmScheduler.exact(this)?"✓ Agendamento exato permitido":"⚠ Sem acesso a alarmes exatos; avisos podem atrasar"),15,WARNING));
        addButton(body,"Permitir notificações",()->{if(Build.VERSION.SDK_INT>=33 && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)!=PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS},1);else notificationSettings();});
        addButton(body,"Permitir alarmes exatos",()->{if(Build.VERSION.SDK_INT>=31){try{startActivity(new Intent(Settings.ACTION_REQUEST_SCHEDULE_EXACT_ALARM,Uri.parse("package:"+getPackageName())));}catch(ActivityNotFoundException e){message("Abra as configurações do Android e permita Alarmes e lembretes para Ymir.");}}else message("Acesso já disponível nesta versão do Android.");});
        addButton(body,"Som e vibração dos avisos",this::notificationSettings);
        addButton(body,"Testar alerta em 10 segundos",()->{AlarmScheduler.test(this);message("Teste agendado. Pode sair do app para conferir o aviso em segundo plano.");});
        addButton(body,"Antecedência dos alertas",()->{EditText value=input("Minutos (0 a 60)",String.valueOf(state.optJSONObject("preferences").optInt("lead_seconds",60)/60),true);new AlertDialog.Builder(this).setTitle("Avisar quantos minutos antes?").setView(value).setNegativeButton("Cancelar",null).setPositiveButton("Salvar",(d,w)->{try{int n=Integer.parseInt(value.getText().toString());if(n<0||n>60)throw new IllegalArgumentException("Use de 0 a 60 minutos.");JSONObject next=store.read();next.getJSONObject("preferences").put("lead_seconds",n*60);save(next);}catch(Exception e){error(e);}}).show();});
        body.addView(label("BACKUP DO PC / ANDROID",18,PURPLE));
        addButton(body,"Importar backup ZIP…",()->startActivityForResult(new Intent(Intent.ACTION_OPEN_DOCUMENT).setType("application/zip").addCategory(Intent.CATEGORY_OPENABLE),20));
        addButton(body,"Exportar backup ZIP…",()->startActivityForResult(new Intent(Intent.ACTION_CREATE_DOCUMENT).setType("application/zip").putExtra(Intent.EXTRA_TITLE,"Ymir-Android-backup.zip").addCategory(Intent.CATEGORY_OPENABLE),21));
        body.addView(label("Importar substitui os dados deste celular após confirmação e cria uma cópia local de segurança. No PC: Ferramentas → Backup → Exportar. Leve o ZIP ao celular. O Windows não é alterado.\n\nPRÉVIA INDEPENDENTE\nO PC pode ficar desligado: os horários já registrados/importados ficam no Android. Marcações posteriores no PC não chegam automaticamente aqui.\n\nPermita notificações e alarmes. O Android ainda pode atrasar avisos por economia de bateria ou configuração do fabricante. Forçar parada desativa os alarmes até reabrir o app. Esta prévia não tem atualização automática nem sincronização em nuvem.",14,MUTED));
    }
    private void notificationSettings() {startActivity(new Intent(Settings.ACTION_CHANNEL_NOTIFICATION_SETTINGS).putExtra(Settings.EXTRA_APP_PACKAGE,getPackageName()).putExtra(Settings.EXTRA_CHANNEL_ID,AlarmReceiver.CHANNEL));}
    @Override public void onRequestPermissionsResult(int request,String[] permissions,int[] grants){super.onRequestPermissionsResult(request,permissions,grants);render();}
    @Override protected void onActivityResult(int request,int result,Intent data) {
        super.onActivityResult(request,result,data);if(result!=RESULT_OK||data==null||data.getData()==null)return;
        try {
            if(request==20){JSONObject candidate;try(InputStream input=getContentResolver().openInputStream(data.getData())){if(input==null)throw new IOException("Arquivo indisponível.");candidate=Store.parseBackup(input);}
                new AlertDialog.Builder(this).setTitle("Substituir dados deste celular?").setMessage("Serão importados "+candidate.getJSONArray("bosses").length()+" bosses e todas as contas do backup. Uma cópia dos dados atuais será guardada neste aparelho. Os horários originais serão mantidos.").setNegativeButton("Cancelar",null).setPositiveButton("Importar",(d,w)->{try{store.importState(candidate);state=candidate;AlarmScheduler.reschedule(this,state);query="";render();message("Backup importado. Confira as permissões de alertas.");}catch(Exception e){error(e);}}).show();
            } else if(request==21){try(OutputStream output=getContentResolver().openOutputStream(data.getData())){if(output==null)throw new IOException("Destino indisponível.");Store.exportState(store.read(),output);}message("Backup exportado.");}
        }catch(Exception e){error(e);}
    }
}
