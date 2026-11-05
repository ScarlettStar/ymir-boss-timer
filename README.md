# Ymir Boss Timer

Aplicativo Windows para acompanhar manualmente os respawns de bosses do Legend of Ymir.

## Funções
- Categorias: Bosses Universais, Bosses Myrkheimr e Bosses Fólkvangr
- Contagens regressivas e horários previstos de nascimento
- Alerta quando falta 1 minuto e no respawn, inclusive com categorias recolhidas
- Modo compacto e histórico de derrotas
- Atualização pelo aplicativo via GitHub Releases

## Como adicionar o código
Envie o arquivo `ymir_boss_timer.py` da versão 1.7 para a **raiz deste repositório**, com esse nome exato. Ele está dentro do ZIP da v1.7.

## Publicação da primeira versão no GitHub
1. Confirme que `ymir_boss_timer.py` aparece na raiz do repositório.
2. Abra **Actions** > **Publicar aplicativo Windows** > **Run workflow**.
3. Informe `1.7.0` (deve ser a mesma versão definida em `APP_VERSION` no código).
4. Execute o workflow. Quando terminar, confira os arquivos em **Releases**: `YmirBossTimer.exe` e `YmirBossTimer.exe.sha256`.
5. Baixe o EXE desta primeira publicação e coloque-o em uma pasta gravável (ex.: Documentos/YmirBossTimer).
6. No aplicativo, abra **ATUALIZAÇÕES**, configure `ScarlettStar/ymir-boss-timer` e clique em **Salvar e verificar**.

Para futuras versões, altere o código e `APP_VERSION` (por exemplo, `1.8.0`) antes de executar **Run workflow** com a mesma versão. O atualizador vai consultar automaticamente o Release mais recente, e, se a opção automática estiver habilitada, instala após dois minutos sem timers ativos.

## Dados e segurança
Os cadastros e históricos são armazenados localmente em `%APPDATA%\YmirBossTimer` e não precisam ser enviados ao GitHub. **Não publique `bosses.json`, `history.json` ou outros dados pessoais**.

O mecanismo de atualização verifica SHA-256 e exige confirmação. O SHA-256 detecta corrupção de download, mas **não autentica** o autor do executável: publique somente código e Releases confiáveis. O sistema ainda precisa ser testado em Windows antes de ser considerado validado.

## v1.9.0 — Myrkheimr por canal
- Myrkheimr agora possui dois subgrupos recolhíveis: **CHN 1** e **CHN 2**.
- Ao abrir a v1.9 pela primeira vez, bosses de Myrkheimr cadastrados nas versões anteriores são preservados no **CHN 1** (incluindo timers e IDs) e duplicados **sem contagem ativa** para o CHN 2.
- Novos bosses cadastrados em Myrkheimr aparecem automaticamente nos dois canais, com cronômetros independentes.
- O histórico e os avisos sonoros/visuais identificam CHN 1 ou CHN 2. Alertas continuam ativos mesmo com os subgrupos recolhidos.
- Executar o workflow **Publicar aplicativo Windows** com a versão `1.9.0`. O workflow executa testes de migração/alertas antes de gerar o executável e o Release.


## Versão 2.0.0

**Fólkvangr por piso:** P1, P2, P3 e P4 UNIVERSAL. Cada boss existe uma vez em cada piso com ID, timer, alertas e histórico próprios. Cadastros anteriores em Fólkvangr ficam no P1 com o timer preservado; os demais pisos recebem cópias sem respawn iniciado. A migração ocorre uma única vez.

**Interface:** aba PRÓXIMOS (ordenada por nascimento), overlay gamer transparente, redimensionamento de opacidade e movimento pelo topo, bandeja do Windows (minimizar, abrir, overlay, sair).

**Notificações:** tentativas de notificação nativa do Windows (winotify) com alerta visual próprio como alternativa, além do som atual. Confirme que as notificações estão permitidas nas Configurações do Windows.

**Backups:** cópia local dos arquivos JSON ao iniciar e a cada seis horas, em \`%APPDATA%\YmirBossTimer\backups\`, com retenção das últimas 12 cópias. Abra essa pasta pelo botão "Abrir backups" na aba Histórico. Nenhum dado dos bosses vai para o GitHub.

**Publicação (3.1):** novas versões na main são publicadas após os testes. Também é possível usar Actions → Publicar aplicativo Windows → Run workflow. Versões existentes não são republicadas. O app verifica Releases ao iniciar e a cada 30 minutos; na versão 2.0, com atualização automática habilitada, instala uma versão pendente após dois minutos sem contagem regressiva ativa. **Uma atualização reinicia o programa**. O atualizador verifica SHA-256, conserva temporariamente o executável anterior e tenta recuperá-lo se o novo processo não inicializar. Não equivale a assinatura digital do executável.

**Primeira atualização de 1.9 para 2.0:** a v1.9 ainda usa o mecanismo manual, então faça essa transição pelo botão "Atualizações → Salvar e verificar → Instalar atualização". As seguintes poderão acontecer sem esse clique, enquanto o aplicativo estiver aberto e sem contagens ativas.

**Notas de uso:** o overlay é uma janela externa sempre no topo, mais compatível com jogos em modo janela sem bordas; não é garantido que apareça sobre tela cheia exclusiva. Para encerrar o programa, use "Sair" no ícone da bandeja. O SmartScreen pode alertar porque o EXE ainda não é assinado. Não desative proteções do Windows. O EXE Windows, a bandeja e as notificações precisam ser validados na máquina do usuário.


## Versão 2.1.0 — editar tempo de respawn

O botão **Editar tempo** aparece no cartão de cada boss na tela completa.
Digite a nova duração em minutos (de 1 a 10080) e clique em **Salvar alterações**.
Para Myrkheimr (CHN 1 e CHN 2) ou Fólkvangr (P1, P2, P3 e P4 UNIVERSAL),
a opção marcada por padrão **Aplicar também a todas as cópias desta região**
altera a duração em todos os canais/pisos do mesmo boss. É possível desmarcar
para editar apenas um canal ou piso.

**Timers já iniciados:** o horário de nascimento é recalculado usando a
última morte de cada cópia (não a hora em que você editou). Os alertas de
1 minuto e de respawn são ajustados à nova previsão. Bosses sem timer
iniciado permanecem aguardando uma morte. O histórico mantém as mortes e
corrige a previsão vinculada à última morte registrada, sem apagar entradas.
Uma cópia de segurança dos dados é criada antes da alteração.

**Publicação:** na 3.1, alterações dos módulos na main publicam novas versões após os testes.
O aplicativo v2.0 verifica as novas versões e instala a v2.1 quando estiver
aberto e sem timers ativos por pelo menos dois minutos (se a opção de
atualização automática estiver habilitada).


## Versão 2.1.1 — correção do instalador

- Corrige a verificação do processo de inicialização do executável \`--onefile\` do PyInstaller: a atualização agora aguarda um marcador escrito pela própria interface, com número da versão, em vez de presumir falha pelo encerramento de um processo intermediário.
- Mantém backup do executável antigo até a nova versão confirmar que abriu, com tentativa de restauração em caso de falha.
- Adiciona arquivo de diagnóstico local em \`%APPDATA%\YmirBossTimer\update.log\`; o PowerShell é gravado com BOM UTF-8 para preservar acentuação no Windows.
- Acrescenta teste de inicialização do EXE ao fluxo de publicação no GitHub Actions, além dos testes unitários.
- **Para quem ficou na v2.0 após um rollback da v2.1:** atualize uma única vez instalando o executável v2.1.1 publicado no Release, com o aplicativo antigo fechado e guardando a cópia do antigo executável. Os arquivos dos bosses permanecem em \`%APPDATA%\YmirBossTimer\`.



## Versão 3.0.0 — central gamer

- Tema compartilhado em azul profundo, verde neon e violeta em todas as janelas.
- Cabeçalho e painel de resumo: cadastros, timers ativos, respawns em até cinco minutos e disponíveis. As contagens incluem seções recolhidas.
- Cards com bordas, faixa de cor, cronômetro ampliado e progresso de respawn.
- Botões com realce ao passar o mouse e foco pelo teclado, sem loops adicionais de animação.
- Mantidos canais, pisos, edição de duração, histórico, backups, alertas, overlay, modo compacto, bandeja e atualizador. Dados continuam no mesmo diretório e formato.
- A publicação agora exige execução manual do workflow; PRs e merges não criam Releases.

### Validação

Execute `python -m unittest discover -s tests -v` e `python -m py_compile ymir_boss_timer.py ymir_features.py ymir_theme.py`.
Para o teste real de interface, use `YMIR_GUI_TESTS=1` em um ambiente com tela (no PowerShell: `$env:YMIR_GUI_TESTS = "1"`). O workflow **Testes do aplicativo** executa esse teste no Windows em PRs, sem publicar uma versão.

Antes de distribuir, revise visualmente no Windows com sua escala de tela e confira som, notificações nativas e bandeja; esses recursos do sistema não são cobertos pelo teste de interface.


## Versão 3.0.1 — reinício independente do atualizador

O processo de atualização solicita um ambiente novo ao PyInstaller antes de abrir o EXE substituído ou restaurado. Evita reutilizar recursos temporários da instância encerrada. O log registra a versão recebida quando há confirmação, inclusive quando difere da esperada.

A versão antiga já instalada continua executando seu próprio atualizador. Se ela restaurar a anterior, feche o aplicativo pela bandeja e abra o executável baixado manualmente pelo Explorer. Não remova os dados em `%APPDATA%\\YmirBossTimer`. A correção passa a proteger futuras atualizações iniciadas pela versão 3.0.1.

CI: além dos testes existentes, gera uma fixture onefile Windows e executa o atualizador real entre dois processos, verificando o log de confirmação. Nenhum Release é criado por esses testes.


## Próxima interface — Central de combate

Navegação lateral fixa com acesso ao radar, histórico, overlay, modo compacto e atualizações. O topo destaca o próximo respawn de todas as regiões, mesmo recolhidas. Cards mostram região/canal/piso, ciclo, última morte, progresso e ações separadas. O cadastro ganhou um painel próprio. Não há alteração no formato dos dados ou na lógica dos timers.

Esta etapa depende da correção de reinício do PR #2. A CI Windows valida interface e reinício onefile e disponibiliza capturas com dados de teste em **Artifacts → interface-preview**. Nenhum Release é publicado automaticamente.


## Versão 3.1.0 — timers inteligentes e atualizações automáticas

- Busca por nome/local sem diferenciar acentos ou maiúsculas. Botão **Filtros** combina região, canal/piso e status; **Só favoritos** e **Limpar** ficam na lista. Filtros não limitam alertas, resumo, modo compacto ou overlay. As seções abrem ao aplicar um filtro e os resultados acompanham mudanças de status.
- Estrela em cada card salva favoritos independentes por canal/piso. Favoritos ficam primeiro dentro das seções e no overlay; o radar global mantém a ordem por horário.
- **Morreu há…** aceita minutos inteiros de 0 a 10080. O respawn parte do horário informado. Histórico é ordenado por morte; mortes já expiradas não repetem avisos antigos.
- Atualização automática: ativa por padrão em instalações novas e respeita a preferência salva. Com o app aberto, verifica ao iniciar e a cada 30 minutos; instala após dois minutos sem timers ativos. Se um timer começar durante o download, adia a instalação. Requer EXE Windows em pasta gravável.
- Falhas de download aguardam 30 minutos antes de tentar novamente. Uma versão que sofreu rollback fica bloqueada para novas instalações automáticas; tentativa manual ou uma versão diferente permite retomar. Erros ficam em update.log.
- Publicação automática no GitHub restaurada: alterações dos módulos na main publicam apenas versões ainda não lançadas, depois de testes e verificação da abertura do EXE. Branches e PRs não publicam.

Para receber esta versão sem baixar pelo navegador: na 3.0.1, deixe marcada a opção automática em **Atualizações**, clique em **Salvar e verificar** para consultar imediatamente e mantenha o app aberto. A instalação espera os timers ativos terminarem. Cadastros, favoritos e histórico permanecem no mesmo diretório.


## Versão 3.2.0 — contas, regiões e respawns variáveis

### Duas ou mais contas

No topo, use **Contas** para salvar o apelido e o servidor da conta atual ou adicionar outra conta. O seletor **Conta / Servidor** troca a tela sem apagar timers. Cadastros antigos ficam em **Conta principal** e podem ser renomeados. Não são necessárias senhas nem acesso ao jogo.

Cada conta tem seus próprios bosses, canais/pisos, favoritos, regiões personalizadas, histórico e observações de respawn. É possível copiar apenas cadastros/regiões para uma nova conta; os IDs são novos, timers ficam zerados e histórico/médias não são copiados. O histórico conserva até 1000 mortes por conta.

A lista, o radar e o modo compacto mostram a conta selecionada. O overlay reúne próximos bosses de todas as contas e identifica conta/servidor; os alertas continuam monitorando todas as contas, mesmo quando outra estiver selecionada. A instalação automática também aguarda os timers das outras contas terminarem.

Metadados ficam em profiles.json, incluído nos backups. Bosses e histórico recebem profile_id mantendo IDs e horários legados. Um arquivo de contas inválido impede a abertura para evitar sobrescrever informações; referências órfãs são recuperadas como contas separadas.

### Regiões e categorias próprias

Use **Regiões → Adicionar região** na conta desejada. Depois cadastre os bosses na nova região. O campo **Categoria** do cadastro aceita valores sugeridos (Boss, Elite, Evento) ou um nome digitado. Os filtros incluem região e categoria. Myrkheimr continua criando CHN 1/2 e Fólkvangr continua criando P1–P4, com timers independentes; regiões novas recebem um cadastro por inclusão.

### Média de respawn

1. Marque **Respawn variável** no cadastro ou **Variável** no card de um boss existente. O tempo manual é a referência inicial.
2. Registre **Boss morreu / Iniciar** ou **Morreu há…**.
3. Ao ver o boss reaparecer, clique **Reapareceu**. Use 0 minutos para agora ou informe há quantos minutos o reaparecimento foi observado.
4. A próxima morte usa a média dos últimos 20 ciclos confirmados desse boss, nessa conta e nesse canal/piso. O card mostra média, quantidade e mínimo/máximo observados.

**Mortes sozinhas não medem respawn:** o intervalo entre duas mortes inclui o tempo em que o boss ficou vivo. O aprendizado usa exclusivamente pares morte → reaparecimento observado. Cada ciclo só pode ser confirmado uma vez. Marque a hora correta de observação para não aumentar artificialmente a média.

Os avisos dos bosses variáveis são **estimativas**, não confirmação de nascimento. O intervalo mínimo/máximo é apenas o observado nos registros. Alternar Variável recalcula a previsão ativa a partir da última morte usando a média ou a referência manual, preservando as observações. Editar a referência não altera horários de reaparecimento já confirmados.

### Validação

Testes de migração, isolamento entre contas/canais/pisos, cópia sem timers/médias, histórico por conta, backup de profiles.json, regiões/categorias e aprendizado por observação. A CI Windows cobre troca de conta, diálogo de observação, criação de região, overlay de ambas as contas, persistência após reabrir e o reinício real do EXE onefile.


## Versão 3.2.1 — Myrkheimr com respawn variável

Todos os bosses de Myrkheimr já cadastrados em todas as contas e em CHN 1/2 recebem Respawn variável uma única vez. A migração preserva IDs, horários em andamento, duração manual, histórico e observações. As médias passam a valer nos próximos registros de morte; contagens já iniciadas mantêm a previsão original. A marca de migração é salva para não repetir a alteração a cada abertura.

Novos cadastros de Myrkheimr e bosses movidos para essa região entram com variável ativado. No cadastro, a opção é marcada automaticamente ao selecionar Myrkheimr. As outras regiões mantêm seu comportamento. O aprendizado continua dependendo de confirmar **Reapareceu**; nenhuma média é inventada a partir de mortes isoladas. A duração manual é usada enquanto não houver observações.


## Versão 3.3.0 — troca rápida de canais

- **Myrkheimr** e **Túmulo do Rei** têm CHN 1 e CHN 2, com IDs, timers, mortes e médias independentes por conta. Túmulo do Rei agora também faz parte das regiões padrão. Nomes já usados como Tumulo do Rei ou Bosses Túmulo do Rei são reconhecidos sem mudar IDs ou nomes cadastrados.
- Acima da lista, use **Todos | CHN 1 | CHN 2**. A escolha afeta apenas a visualização de Myrk/Túmulo; Universais, Fólkvangr e outras regiões continuam visíveis. A escolha fica salva por conta e também está disponível no modo compacto.
- Trocar o canal não reinicia nem move timers. Alertas e overlay continuam monitorando os dois canais de todas as contas. O resumo/radar mantém a visão de todos os canais da conta selecionada. **Limpar** restaura Todos e limpa os filtros; trocar de conta mantém a escolha salva daquela conta.
- Bosses antigos de Túmulo sem canal são preservados no CHN 1. A cópia do CHN 2 começa sem contagem e sem observações, sem inventar mortes. Se o CHN 2 já existir, ele não é duplicado. Cadastros novos criam as duas cópias.
- O histórico identifica o canal em ambas as regiões, e edições em lote continuam limitadas à conta/região/categoria. A configuração variável de Túmulo é preservada; Myrk continua variável por padrão conforme a 3.2.1.


## Versão 3.4.0 — completar o Túmulo e avisos visíveis

A atualização completa automaticamente as cópias que faltarem do CHN 1 do Túmulo para o CHN 2, inclusive quando o cadastro já tinha o canal 1 informado. Preserva os nomes, categoria, modo de respawn e tempo manual; gera IDs novos e inicia timers/histórico/observações do CHN 2 zerados. Bosses já existentes no CHN 2 são preservados, sem duplicar ou substituir seus tempos/médias.

O botão **Copiar Túmulo → CHN 2**, ao lado da troca rápida de canal, permite completar novamente os cadastros da conta selecionada. Repetir a ação não duplica bosses. A migração inicial é marcada para não recriar automaticamente uma cópia que você remover depois; o botão permite refazê-la explicitamente.


### Avisos na tela e som

Os alertas de um minuto e de respawn passam a abrir **sempre** um painel flutuante no canto inferior direito, além do som. Mostra nome do boss, conta/servidor, região/canal e contagem. Avisos variáveis são identificados como previsão. Funciona com o app na bandeja ou no modo compacto; notificações nativas do Windows continuam adicionais, sem substituir o painel.

Avisos simultâneos ficam no mesmo painel com rolagem; o painel fecha após 20 segundos desde o aviso mais recente ou pelo X. No Windows usa janela sem ativação para evitar tomar o foco durante o jogo. O botão **Testar aviso** permite conferir som e painel sem registrar mortes ou alterar timers.


## Versão 3.5.0 — ferramentas para jogar

- **Mini painel:** abra Overlay gamer. Redimensione pelas bordas, arraste pelo topo e ajuste a opacidade. Posição, tamanho e opacidade ficam salvos ao fechar. Clique em uma linha ou escolha um boss no seletor para usar Matei/Reapareceu. O seletor inclui bosses ainda sem timer; o painel mostra contas e servidores. Trocar canal limita a visualização sem suspender alertas globais.
- **Atalhos:** Ctrl+Alt+O abre/fecha o painel, K registra morte, R confirma reaparecimento variável, C alterna CHN 1/2. K/R exigem seleção explícita, que é apagada ao trocar conta/canal. Em Ferramentas → Atalhos, ative os atalhos globais do Windows para usar com o jogo em foco. Se outro programa reservar uma combinação, o app informa o conflito. Atalhos e painel podem depender do modo de janela e dos privilégios do jogo.
- **Previsão variável:** mantém média, mínimo/máximo e número de observações, acrescentando a faixa de horários do ciclo baseada nos registros e indicação de poucas amostras. A faixa observada não garante o nascimento; registre Reapareceu para alimentar a média.
- **Alertas:** Ferramentas → Alertas permite antecedência de 0 a 60 minutos, volume do próprio app e sons Cristal/Grave/Duplo. Configure o padrão ou um boss da conta selecionada; canais têm IDs e opções independentes. Volume 0 desliga só o som. Antecedência 0 mantém o aviso no horário. Pausar conta silencia som e avisos por 30 minutos; as contagens continuam. Avisos suprimidos não são repetidos ao reativar.
- **Backup:** Ferramentas → Backup exporta ZIP com todas as contas, bosses, timers, histórico e configurações. Restaurar valida antes de escrever, pede confirmação e cria um backup dos dados atuais. Falha de escrita tenta reverter os arquivos. Contagens restauradas usam horários originais. Backups automáticos também incluem preferences.json.
- **Resumo:** Ferramentas → Contas/canais reúne todas as contas por região/canal/piso e atualiza as contagens a cada segundo.

Atualização automática preservada.


## Sincronização gratuita Windows / Android (em validação)

A conexão opcional usa Firebase Spark, Authentication por e-mail/senha e Firestore, sem Functions ou faturamento. Configuração e limites em [cloud/README.md](cloud/README.md). Windows: Ferramentas → Nuvem; Android: Ajustes → Conectar à nuvem. O projeto precisa ser configurado uma vez antes de usar o mesmo login nos dois aparelhos.
