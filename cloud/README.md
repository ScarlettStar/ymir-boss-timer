# Sincronização gratuita — configuração necessária

Esta implementação usa somente Firebase Authentication (e-mail/senha) e Firestore Standard no plano **Spark**. Não ative Blaze, Functions, Storage ou serviços de agendamento pagos. A aplicação não cria nem altera faturamento.

## Configurar uma vez

1. Entre em https://console.firebase.google.com/ com sua conta Google.
2. Crie o projeto **Ymir Boss Timer**. Google Analytics é opcional; pode deixar desativado.
3. Confira que está no plano **Spark**, sem vincular cartão/faturamento.
4. Em **Authentication → Sign-in method**, habilite **E-mail/senha** (senha, não link por e-mail).
5. Em **Firestore Database**, crie um banco **Standard**, ID `(default)`, em **modo de produção**. Escolha a localização com cuidado; ela é permanente.
6. Em **Firestore → Regras**, copie o conteúdo de `cloud/firestore.rules` e publique. Não use regras públicas nem modo de teste.
7. Em **Configurações do projeto → Geral**, registre um app **Web** (ícone `</>`), sem Hosting. Copie somente `projectId` e `apiKey` da configuração pública do app. Não gere chave de conta de serviço.
8. No Windows: **Ferramentas → Nuvem**. Informe projeto, Web API Key, e-mail e uma senha própria; clique **Criar login** e depois **Sincronizar agora**. Espere a confirmação de sincronização.
9. No Android: **Ajustes → Conectar à nuvem**. Use o mesmo projeto, chave, e-mail e senha e deixe **Criar novo login** desmarcado. Toque **Sincronizar agora** e confira contas e horários.
10. Faça um teste com um boss de teste: marque no PC, sincronize nos dois, confirme no celular; repita no sentido inverso. Teste também sem conexão e com aparelhos em contas/canais diferentes.

Alternativa para desenvolvedores: `firebase deploy --only firestore --project SEU_PROJECT_ID` publica regras e desativa a indexação desnecessária do payload. A etapa exige login autorizado no projeto. O cliente também funciona com as regras publicadas manualmente.

## Limites e funcionamento

- O app consulta a nuvem a cada 60 segundos enquanto aberto. Android também pede ao JobScheduler uma consulta periódica de pelo menos 15 minutos, com rede disponível. O sistema pode adiar essa execução. Não há promessa de atualização imediata em segundo plano.
- Depois de recebidos os horários, os alarmes são locais e funcionam sem PC e sem conexão, dependendo das permissões do Android. Forçar parada impede alarmes e tarefas até reabrir.
- Marcar no celular solicita sincronização imediata; no PC a consulta seguinte leva até aproximadamente um minuto. A rede pode acrescentar atraso. Falhas preservam dados e tentam novamente, sem ativar cobrança.
- Compartilha contas, regiões, bosses, favoritos, contagens, histórico e amostras de respawn. Não compartilha seleção de conta/canal, sons, volume, antecedência, mute, atalhos, atualização ou posição de janelas. A própria entrega dos avisos é local por aparelho.
- Alterações em bosses diferentes são combinadas. Alterações simultâneas conflitantes no mesmo boss mantêm o dado já confirmado na nuvem; a alternativa local fica em `cloud-base.json`, lista `conflicts`. Não se infere um novo respawn a partir de morte em outro aparelho.
- A gravação usa a versão do documento (`updateTime`) para não sobrescrever uma atualização que chegou durante a consulta. Não grava quando não há mudanças.
- Um documento por login, limite conservador de 850 KB. Histórico compartilhado limitado aos 1000 registros mais recentes. Se atingir o limite, o app informa a falha e preserva os dados locais. As cotas do Spark são limites de uso, não garantia de disponibilidade ilimitada.
- O usuário inicial do Firebase é separado das contas do jogo. Nenhuma senha do jogo é solicitada. Todos os perfis locais são enviados ao login escolhido após confirmação.
- Senhas não são salvas. Refresh tokens são protegidos pelo DPAPI do Windows e Android Keystore; não entram nos backups ZIP nem no Git. A chave Web API é configuração pública, não substitui autenticação nem regras.
- Antes de aplicar mudanças remotas, os apps validam os dados e criam backup local. Importações e restaurações manuais também se tornam alterações pendentes de sincronização; exporte um ZIP antes de importar uma coleção antiga.

## Estado de entrega

O código e os testes podem ser preparados sem um projeto real. A conexão entre aparelhos só estará ativa após o projeto, Authentication e regras serem configurados e o mesmo login ser usado nas duas versões novas. Testes com transporte simulado/emuladores não substituem essa validação final.
