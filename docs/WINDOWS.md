# Serviço Windows 10 com WinSW

## Preparação

Use uma pasta dedicada, por exemplo `C:\Services\MinecraftDiscordBot`, e Python 3.13 x64 instalado para todos os usuários. O Python da Microsoft Store e instalações privadas dentro de um perfil podem não estar acessíveis à conta de serviço. O `.venv` referencia a instalação base do Python; não basta dar acesso somente à pasta do projeto se o interpretador base estiver em outro local restrito.

Os scripts são compatíveis com PowerShell 5.1. Se a política bloquear um script revisado, execute-o com `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...`. Isso vale só para aquele processo e não altera permanentemente a política do computador.

Execute `Setup.ps1` e preencha `.env`, inclusive TLS. Rode `check`, `doctor` e o bot manualmente antes de instalar o serviço. As credenciais não são enviadas pelo instalador a nenhum serviço além dos acessos normais feitos pelo próprio bot quando iniciado.

## Instalar

Em PowerShell elevado, na pasta do projeto:

```powershell
.\scripts\Install-Service.ps1
.\scripts\Start-Service.ps1
Get-Service MinecraftDiscordBot
```

O instalador:

1. Valida a configuração local. Exige `DATA_DIR=data` e `LOG_DIR=logs` para que as ACLs correspondam aos diretórios corretos.
2. Baixa **somente WinSW 2.12.0 x64**, do [release oficial](https://github.com/winsw/winsw/releases/tag/v2.12.0), verificando SHA-256 `05b82d46ad331cc16bdc00de5c6332c1ef818df8ceefcd49c726553209b3a0da`.
3. Gera `service/MinecraftDiscordBot.xml` com caminhos absolutos e diretório de trabalho explícito.
4. Restringe a ACL da pasta dedicada e reinicializa a herança dos arquivos. Operador, Administrators e SYSTEM têm controle total; LocalService tem leitura/execução. LocalService recebe gravação apenas em `data` e `logs`. Isso protege `.env` de outros usuários Windows comuns. O script recusa links/reparse points na árvore.
5. Registra o serviço **MinecraftDiscordBot** como `NT AUTHORITY\LocalService`, sem senha e sem execução administrativa cotidiana.

O serviço é instalado parado. `Start-Service.ps1` o inicia explicitamente. O início no próximo boot é automático atrasado. Falhas reiniciam o bot após 30, 60 e 120 segundos; as seguintes repetem 120 segundos. Não há reboot automático do Windows.

O wrapper executa Python na sessão de serviços, sem janela interativa, foco ou bandeja. Não usa Windhawk. Pode continuar após logout, desde que o computador esteja ligado e a rede disponível. O bot não mantém o PC acordado e não continua durante suspensão/hibernação.

**Crafty é independente.** Se sua inicialização atual do Crafty acontece somente depois de login, o bot pode estar ativo antes disso e mostrar indisponibilidade. Se logout encerrar o Crafty por causa da configuração existente, o bot não o recupera. O instalador não muda esse comportamento.

LocalService é uma conta de baixo privilégio compartilhada com outros serviços locais. Ela não é uma fronteira de segurança contra administradores do computador nem contra um serviço comprometido na mesma conta. Para este cenário doméstico, evita usar LocalSystem ou sua conta pessoal com privilégios amplos. O acesso de rede do bot é somente de saída para Discord e local para Crafty/Minecraft.

## Controlar e desinstalar

Todos estes comandos são executados em PowerShell elevado:

```powershell
.\scripts\Stop-Service.ps1
.\scripts\Start-Service.ps1
.\scripts\Restart-Service.ps1
.\scripts\Uninstall-Service.ps1
```

Eles operam **apenas o serviço MinecraftDiscordBot**. Parar/desinstalar o bot não para Minecraft nem Crafty. A desinstalação preserva código, `.env`, certificados, logs, estado e ACLs.

Na parada, WinSW inicia o helper `python -m minecraft_bot stop`, que grava `data/stop.request`. O bot verifica esse arquivo a cada dois segundos, cancela tarefas de consulta/espera, fecha Discord e HTTP e libera a trava. O diário de um comando já enviado fica preservado. WinSW aguarda até 45 segundos; em travamento do bot, o wrapper pode terminar somente seu processo Python. Nenhum processo Minecraft/Crafty pertence à árvore do bot.

Não edite `.env` para um conteúdo inválido enquanto o serviço estiver em execução: o helper também lê a configuração. Pare antes de alterar. Em emergência, o timeout do wrapper continua limitado ao bot.

## Diagnóstico

```powershell
Get-Service MinecraftDiscordBot
Get-Content -LiteralPath .\logs\bot.jsonl -Tail 50 -Wait
Get-ChildItem -LiteralPath .\logs
```

| Sintoma | Verificação |
|---|---|
| Serviço inicia e logo para | `.env`, Python base acessível, dependências, logs do wrapper |
| Funciona no terminal, falha como serviço | Certificado fora da pasta sem leitura para LocalService; Python instalado apenas no perfil; caminhos de dados personalizados |
| Discord online, Crafty indisponível | Crafty aberto? TLS/pin/porta? Token válido? Fuso correto? UUID correto? |
| Falha `PermissionError` | ACL do projeto, `data` e `logs`; não execute duas cópias |
| Falha `ValueError` no início | Use `.env.example` como referência; IDs distintos, URL HTTPS local, UUID, limites numéricos e estado compatível |
| Canal/painel não aparece | ID da guild/canal e quatro permissões Discord; histórico precisa estar acessível |
| Dados antigos | Horário do Windows, `CRAFTY_TIMEZONE`, frequência de stats e saúde do Crafty |
| Ação permanece incerta | Siga o procedimento de reconciliação no README; não apague o diário por tentativa |

Para mudar a pasta de instalação, pare e desinstale o serviço, copie os arquivos para a nova pasta dedicada, recrie `.venv` e reinstale. O XML tem caminhos absolutos; não mova a instalação ativa.

## Atualização e ZIP

O projeto não baixa executáveis ou dependências enquanto está em execução. Downloads ocorrem somente nos scripts explícitos de preparação/instalação/testes. Não há tarefa agendada paralela.

`scripts/Package.ps1` gera `dist/Minecraft-Discord-Crafty.zip` com uma lista permitida de fontes, docs e testes. Exclui `.env`, certificados, estado, logs, ambiente virtual e executáveis baixados. O ZIP final não precisa do WinSW embutido; o instalador o baixa com hash verificado.

Referência: [WinSW 2.12: conta, parada, recuperação e configuração](https://github.com/winsw/winsw/blob/v2.12.0/doc/xmlConfigFile.md).
