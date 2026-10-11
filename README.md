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

Para futuras versões, altere o código e `APP_VERSION` (por exemplo, `1.8.0`) antes de executar **Run workflow** com a mesma versão. O atualizador vai consultar automaticamente o Release mais recente, mas só instala após confirmação.

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

**Atualizações automáticas:** a publicação no GitHub acontece automaticamente quando uma nova versão é gravada em \`ymir_boss_timer.py\` no ramo \`main\`, desde que o workflow passe pelos testes. O app verifica Releases ao iniciar e a cada 30 minutos; na versão 2.0, com atualização automática habilitada, instala uma versão pendente após dois minutos sem contagem regressiva ativa. **Uma atualização reinicia o programa**. O atualizador verifica SHA-256, conserva temporariamente o executável anterior e tenta recuperá-lo se o novo processo não inicializar. Não equivale a assinatura digital do executável.

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

**Atualização:** o código publica automaticamente pelo GitHub Actions.
O aplicativo v2.0 verifica as novas versões e instala a v2.1 quando estiver
aberto e sem timers ativos por pelo menos dois minutos (se a opção de
atualização automática estiver habilitada).


## Versão 2.1.1 — correção do instalador

- Corrige a verificação do processo de inicialização do executável \`--onefile\` do PyInstaller: a atualização agora aguarda um marcador escrito pela própria interface, com número da versão, em vez de presumir falha pelo encerramento de um processo intermediário.
- Mantém backup do executável antigo até a nova versão confirmar que abriu, com tentativa de restauração em caso de falha.
- Adiciona arquivo de diagnóstico local em \`%APPDATA%\YmirBossTimer\update.log\`; o PowerShell é gravado com BOM UTF-8 para preservar acentuação no Windows.
- Acrescenta teste de inicialização do EXE ao fluxo de publicação no GitHub Actions, além dos testes unitários.
- **Para quem ficou na v2.0 após um rollback da v2.1:** atualize uma única vez instalando o executável v2.1.1 publicado no Release, com o aplicativo antigo fechado e guardando a cópia do antigo executável. Os arquivos dos bosses permanecem em \`%APPDATA%\YmirBossTimer\`.
