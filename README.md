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
