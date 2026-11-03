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

**Publicação manual (3.0):** alterações e merges não publicam Releases. Use Actions → Publicar aplicativo Windows → Run workflow quando decidir distribuir uma versão. O app verifica Releases ao iniciar e a cada 30 minutos; na versão 2.0, com atualização automática habilitada, instala uma versão pendente após dois minutos sem contagem regressiva ativa. **Uma atualização reinicia o programa**. O atualizador verifica SHA-256, conserva temporariamente o executável anterior e tenta recuperá-lo se o novo processo não inicializar. Não equivale a assinatura digital do executável.

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

**Publicação:** a partir da 3.0, o GitHub Actions publica apenas por execução manual.
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
