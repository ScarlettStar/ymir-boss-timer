# Boss Auto, Windows e celular

O painel **Caça** no Android e **Caça ao vivo** no Windows mostra mapa, boss, canal, etapa, próximo destino, contadores e últimos registros do Boss Auto. Atualiza a cada 15 segundos com a aba aberta; após 90 segundos sem atualização, a atividade é marcada desatualizada. Não é vídeo nem controle remoto.

## Ativar
1. Atualize os três aplicativos preservando os dados. Não desinstale o Android anterior para atualizar.
2. Entre na nuvem do Timer com o mesmo login nos dispositivos e sincronize suas contas/servidores.
3. No Boss Auto, abra **Conectar Timer / celular**, entre com esse login e escolha a conta/servidor correto.
4. Vincule cada boss/canal ao cadastro correspondente. **Cadastrar os não vinculados no Timer** pede confirmação e cria somente cadastros, sem iniciar contagens. Salve antes de iniciar a caça.
5. No Firebase Console do projeto proprietário, abra Firestore Database → Regras e publique o conteúdo completo de `cloud/firestore.rules`. As regras mantêm os timers existentes e liberam o painel privado somente ao proprietário autenticado. Sem a publicação, os timers podem sincronizar, mas o painel será recusado.
6. No celular, abra **Caça** na mesma conta. O painel identifica o PC que enviou a atividade.

## Dados e limites
- Senha não é salva. A sessão do Boss Auto é protegida pelo Windows DPAPI; configure o login separadamente em cada PC. Não copie `timer-session.bin` entre máquinas.
- Dê um nome diferente a cada PC. Arduino continua conectado somente à máquina executando o jogo.
- A fila persiste sem internet; eventos identificados evitam duplicação. Morte antiga não substitui correção manual posterior do Timer.
- Mortes por observação do bot são estimadas. Combate inconclusivo não inicia timer; vincular não envia histórico antigo.
- Os mapas do Desfiladeiro com respawn fixo usam 10 minutos; outros seguem a janela configurada.
- Atividade exige programa aberto e vinculado. Dados atrasados nunca devem ser interpretados como caça atual.

## Validação
Testes cobrem isolamento entre contas/canais, repetição sem duplicar, conflitos com correção manual, fila persistente e atividade antiga. A ativação real exige publicar as regras e entrar com o login proprietário nos aplicativos.
