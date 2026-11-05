# Ymir Android 0.2 — prévia com nuvem gratuita

App Android nativo, Android 8+ (API 26), com notificações agendadas no próprio celular. Não depende do PC ligado ou de conexão com a internet após registrar/importar os horários.

## O que funciona

- Contas/servidores isolados, regiões/categorias personalizadas e canais/pisos independentes.
- Registrar morte, zerar/editar contagem, observar reaparecimento variável e média das últimas 20 observações reais.
- Lista de próximos respawns, busca, filtro de canais e resumo por conta.
- AlarmManager, notificações com boss/conta/servidor/canal, som e vibração configurados no Android.
- Recuperação de alarmes após reinício/atualização e concessão de permissão.
- Importação/exportação ZIP compatível com o backup do Windows 3.5. Confirmação antes de substituir dados, validação e cópia privada de segurança (últimas 6 importações).
- Preserva preferências do desktop para ida/volta; antecedência por boss e pausa por conta importadas são respeitadas. Volume/sons do aviso Android são controlados pelo canal de notificação do sistema, não pelo mixer do PC.

## Instalar / usar a prévia

1. Baixe o APK no artefato `Ymir-Android-preview` da execução Android no GitHub. É uma compilação de teste assinada com a chave debug do runner, sem Play Store e sem atualizações automáticas.
2. Abra o APK no celular e permita a instalação por essa origem quando o Android solicitar.
3. Em Ajustes, permita notificações e alarmes exatos. Configure som/vibração e faça o teste de 10 segundos com a tela do app fechada.
4. Conecte a nuvem gratuita em Ajustes para receber contas e bosses do PC. Como alternativa offline, cadastre-os ou importe um backup ZIP.
5. No celular, registre Matei e depois Reapareceu somente quando observar o nascimento real. Não há interação automática com o jogo.

**Sincronização opcional:** configure o mesmo projeto Firebase Spark e login no Windows e no Android. Veja [o passo a passo da nuvem](../cloud/README.md). Esta versão solicita INTERNET somente para Authentication/Firestore. Alertas continuam locais; abrir o app consulta os horários imediatamente e o sistema tenta consultas periódicas em segundo plano. O Android pode adiar essas consultas. Nenhuma configuração de faturamento é criada.

Alarmes dependem do celular ligado e das permissões/configurações do Android. Sem acesso a alarmes exatos usa agendamento aproximado e informa na tela. Economia de bateria/Doze/fabricante podem atrasar avisos, mesmo com permissão. Forçar parada impede entrega até reabrir. Alertas encerrados há mais de 15 minutos não são repetidos ao reabrir/reiniciar/importar. Privacidade de conteúdo na tela bloqueada é configurada pelo Android.

O APK debug é destinado a teste inicial. Uma chave de assinatura estável privada deve ser configurada no CI antes de distribuir atualizações instaláveis por cima; não inclua chaves no repositório. Publicações Android devem ser pré-releases e nunca substituir `latest` do Windows (o atualizador desktop consulta esse endpoint).

## Build / testes

JDK 17, SDK 35 e Gradle 8.11.1. Abra `android/` no Android Studio ou use `gradle testDebugUnitTest lintDebug assembleDebug`. `connectedDebugAndroidTest` verifica backup, isolamento e entrega real de notificação pelo AlarmManager com a Activity em segundo plano, em emulador API 35.

Fontes oficiais: [alarmes](https://developer.android.com/develop/background-work/services/alarms), [permissão de notificações](https://developer.android.com/develop/ui/views/notifications/notification-permission), [AGP 8.9](https://developer.android.com/build/releases/agp-8-9-0-release-notes).
