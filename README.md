# Minecraft Survival — Painel de Controle

### Esse bot foi feito para minhas necessidades de uso, para agilizar tarefas que eu faria manualmente.

Bot Python para **dois usuários autorizados por ID Discord**, com painel persistente e controle do **Minecraft Java Vanilla pela API v2 do Crafty**. Feito para Windows 10 x64 e Python 3.13 x64.

O bot **nunca abre, encerra ou reinicia Crafty.exe**, nunca executa Java e não configura a inicialização do Crafty. Ao iniciar o bot, apenas consulta o estado. Minecraft continua desligado até uma ação autorizada no Discord ou uma ação manual no Crafty.

## O que está incluído

- Uma mensagem com embed e botões persistentes **Ligar**, **Desligar**, **Atualizar**.
- Allowlist exata, restrição de guild/canal/mensagem, respostas privadas, cooldown e confirmação com validade de 30 segundos.
- Parada apenas após duas verificações de servidor vazio, incluindo status local do Minecraft. Informação desconhecida bloqueia a parada.
- TLS obrigatório: CA confiável ou pin SHA-256 do certificado. API e status Minecraft restritos a loopback.
- Diário JSON atômico para IDs do painel e operações em andamento; nenhuma necessidade de SQLite.
- Reconciliação após falha/reinício e bloqueio de comandos com resultado incerto.
- Serviço WinSW como **LocalService**, início automático atrasado, reinício em falha e parada graciosa do bot.
- Logs JSON com rotação, dependências fixadas com hashes, testes sem Minecraft/Discord reais e scripts PowerShell.

**Limites importantes:** a API não oferece uma transação “pare somente se ainda estiver vazio”. Pode entrar alguém entre a última consulta e a parada, e o status Vanilla também pode ter um pequeno cache. Não existe garantia absoluta contra essa corrida com as interfaces utilizadas. Não entre durante a confirmação. O estado **Pausado** não é inferido: servidor vazio não prova pausa. Consulte [segurança e decisões](docs/SEGURANCA.md).

## Começo rápido

1. Extraia o ZIP em uma pasta dedicada, por exemplo `C:\Services\MinecraftDiscordBot`. Não instale na raiz de um disco nem em uma pasta com outros projetos: o instalador restringe as permissões dessa pasta e de seu conteúdo.
2. Instale **Python 3.13 x64** pelo [site oficial](https://www.python.org/downloads/windows/). Para serviço, prefira instalação **para todos os usuários** em `C:\Program Files\Python313`, com `pip`, `venv` e launcher. Não use o alias da Microsoft Store. Este projeto fixa a linha 3.13; use a atualização de manutenção disponível dessa linha.
3. Abra PowerShell na pasta do projeto e execute:

```powershell
Set-Location -LiteralPath 'C:\Services\MinecraftDiscordBot'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Setup.ps1
```

Se o launcher `py` não estiver disponível:

```powershell
.\scripts\Setup.ps1 -PythonExe 'C:\Program Files\Python313\python.exe'
```

4. Preencha o `.env` criado pelo script. Siga [Discord](docs/DISCORD.md) e [Crafty/TLS](docs/CRAFTY.md). Os tokens ficam **somente no seu computador**; não os envie a chats nem a repositórios.
5. Confira a configuração e a integração de leitura:

```powershell
.\.venv\Scripts\python.exe -m minecraft_bot check
.\.venv\Scripts\python.exe -m minecraft_bot list-servers
.\.venv\Scripts\python.exe -m minecraft_bot doctor
```

`list-servers` aceita o UUID provisório do exemplo enquanto você descobre o correto. Preencha todos os demais campos obrigatórios. Depois substitua `CRAFTY_SERVER_ID` e execute `doctor`. Nenhum desses comandos liga ou desliga o Minecraft. Pare uma instância do bot antes de usar `doctor` ou `list-servers`, pois compartilham a trava local.

6. Rode uma vez em primeiro plano para conferir o painel:

```powershell
.\.venv\Scripts\python.exe -m minecraft_bot run
```

O painel é criado automaticamente no canal configurado. Use `Ctrl+C` para parar **o bot**; o Minecraft e o Crafty mantêm seus próprios estados. Não execute o bot manualmente ao mesmo tempo que o serviço.

7. Em PowerShell **como administrador**, instale e inicie **somente o serviço do bot**:

```powershell
Set-Location -LiteralPath 'C:\Services\MinecraftDiscordBot'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Install-Service.ps1
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Start-Service.ps1
Get-Service MinecraftDiscordBot
```

O instalador baixa WinSW 2.12.0 x64 do repositório oficial e confere um SHA-256 fixado. Se a validação falhar, interrompe. [Instruções completas do serviço](docs/WINDOWS.md).

## Configuração

O `.env.example` contém todos os parâmetros. Caminhos relativos são resolvidos contra a pasta do projeto, independentemente do diretório do terminal. Variáveis de ambiente existentes têm precedência sobre `.env`.

| Variável | Uso |
|---|---|
| `DISCORD_TOKEN` | Token do bot, nunca um token de conta pessoal |
| `OWNER_DISCORD_ID`, `FRIEND_DISCORD_ID` | Dois IDs numéricos distintos; nenhum bypass por cargo/admin |
| `DISCORD_GUILD_ID`, `DISCORD_CHANNEL_ID` | Servidor Discord e canal de texto exclusivo do painel |
| `CRAFTY_URL` | Ex.: `https://127.0.0.1:8443`, sem `/api/v2` |
| `CRAFTY_TOKEN` | Token de usuário dedicado com acesso a um servidor e COMMANDS |
| `CRAFTY_SERVER_ID` | UUID interno, não nome do mundo nem porta |
| `CRAFTY_VERSION` | `4.11.0`, versão informada e usada na conferência do código oficial |
| `CRAFTY_CA_FILE` | Caminho de CA/PEM confiável; alternativa ao pin |
| `CRAFTY_CERT_SHA256` | Pin do certificado público local; alternativa à CA |
| `CRAFTY_TIMEZONE` | Fuso usado pelo processo Crafty nas datas sem offset; padrão `America/Sao_Paulo` |
| `MC_STATUS_HOST`, `MC_STATUS_PORT` | Loopback e porta do mesmo Minecraft selecionado no Crafty |
| `POLL_SECONDS` | Padrão 30; mínimo 30 segundos |
| `STATS_MAX_AGE_SECONDS` | Padrão 90; dados mais antigos bloqueiam controles |
| `HTTP_TIMEOUT_SECONDS`, `STATUS_TIMEOUT_SECONDS` | 10 e 5 segundos por consulta |
| `START_TIMEOUT_SECONDS`, `STOP_TIMEOUT_SECONDS` | 240 e 300 segundos para confirmação; não matam processos |
| `OPERATION_POLL_SECONDS` | Consulta a cada 10 segundos durante uma operação |
| `CONFIRM_SECONDS`, `COOLDOWN_SECONDS` | 30 e 10 segundos |
| `PANEL_HEARTBEAT_SECONDS` | Publica uma checagem recente a cada 300 segundos, mesmo sem mudanças |
| `DATA_DIR`, `LOG_DIR` | Padrão `data`, `logs`; o instalador do serviço exige esses caminhos locais |

A confirmação real de inicialização exige nova estatística `running=true` **e resposta de status local**. A de desligamento exige nova estatística `running=false` e ausência de resposta local. HTTP 200 da ação, sozinho, significa apenas que o pedido foi aceito.

## Como o painel se comporta

Os dados são consultados a cada 30 segundos enquanto o Crafty está acessível. Em falha, o intervalo de tentativas cresce de 30 para 60, 120, 240 e até 300 segundos; cliques não contornam esse backoff. Ao recuperar a conexão, o intervalo normal retorna. Uma operação usa consultas a cada 10 segundos, sem um segundo poller simultâneo.

O painel edita a mesma mensagem quando algum dado muda. O horário exibido é a **última consulta bem-sucedida publicada**, não uma promessa de que uma mensagem sem edição continua atual. Para evitar editar apenas por causa do relógio, consultas sem mudança são publicadas no heartbeat de 5 minutos. Timestamps relativos de atividade são renderizados pelo Discord. `Atualizar` consulta imediatamente quando não há backoff, mas não força uma edição idêntica.

Se a mensagem for excluída, ela é recriada no próximo ciclo. Se o bot morrer depois de enviar uma mensagem e antes de guardar seu ID, procura sua própria marca no histórico antes de criar outra. Por isso **Read Message History** é obrigatório. A busca inicial percorre o histórico; use um canal dedicado com poucas mensagens. A trava de instância cobre uma instalação; não rode outra cópia em outra pasta/computador com o mesmo token/canal.

Se o canal desaparecer ou suas permissões forem removidas, o bot registra o problema e tenta de novo. Não cria canais nem migra para outro canal automaticamente. A conexão Discord usa a reconexão de `discord.py`; falhas de gateway não iniciam ou param o Minecraft.

Versão, nomes e tempo de atividade ausentes aparecem como **Indisponível**. A lista retornada pelo status pode ser apenas uma amostra; ela é identificada quando incompleta. `Vanilla` é o software **configurado por você**, não uma detecção de marca pelo protocolo. Estados externos sem evidência suficiente aparecem como indisponíveis, sem adivinhar se há uma inicialização ou parada manual.

## Logs, testes e atualização

```powershell
Get-Content -LiteralPath .\logs\bot.jsonl -Tail 30 -Wait
powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\scripts\Test.ps1
```

`bot.jsonl` tem até 2 MB, com cinco arquivos anteriores. Eventos de auditoria usam `logger=audit`, ID do usuário, ação e resultado. Tokens, corpos HTTP e mensagens arbitrárias de exceções não são incluídos. WinSW tem rotação própria para seus logs. [Verificações realizadas e limites](docs/VALIDACAO.md).

Para atualizar: pare o serviço, faça uma cópia privada de `.env`, `data` e certificados, extraia a nova versão sem sobrescrever esses dados, execute `Setup.ps1`, `Test.ps1` e `doctor`, depois inicie o serviço. Preserve `data/state.json`: ele contém o ID da mensagem e o diário. Se mudar de caminho, desinstale/reinstale o serviço e recrie `.venv`; ambientes virtuais não são portáveis.

Para atualizar dependências, altere as faixas em `pyproject.toml` quando necessário e gere novamente os locks com `uv pip compile pyproject.toml --generate-hashes -o requirements.txt` e `uv pip compile pyproject.toml --extra dev --generate-hashes -o requirements-dev.txt`, usando Python 3.13 no Windows. Execute os testes antes de distribuir. O bot não tem atualizador automático.

## Recuperação de uma operação incerta

Uma ação pode ter sido recebida mesmo se a resposta HTTP se perder. O bot **não reenvia** o POST, nem ao reiniciar. Continua observando e libera os controles se conseguir confirmar o estado alvo com dados coletados depois do pedido.

Se o resultado nunca puder ser confirmado:

1. Pare o serviço do bot.
2. Confira manualmente no Crafty o estado e o console do servidor. Aguarde qualquer ação enfileirada, inicialização, salvamento ou desligamento terminar. Resolva conectividade/token/fuso, se necessário. Não limpe o diário enquanto a ação original ainda puder executar.
3. Execute `doctor` e confirme que os dados refletem a situação real.
4. Apenas depois da verificação, libere o diário:

```powershell
.\.venv\Scripts\python.exe -m minecraft_bot clear-pending --verified-in-crafty
```

5. Inicie o bot novamente. Esse comando local não envia ações ao Crafty e preserva o ID do painel. A opção indica uma verificação humana; o programa não consegue comprová-la.

Se `state.json` estiver corrompido, o bot falha de forma conservadora. Restaure seu backup. Sem backup, confira manualmente operações pendentes, pare o serviço e arquive o arquivo inválido antes de iniciar; a mensagem poderá ser recuperada pela marca no histórico. Para trocar guild/canal/UUID, pare o bot, resolva operações pendentes e arquive o estado antigo; remova manualmente o painel antigo no Discord para não deixar uma mensagem obsoleta.

## Estrutura

```text
minecraft_bot/
  __main__.py       CLI, ciclo de vida e parada do bot
  config.py         .env e validação
  crafty.py         HTTP/TLS e endpoints fechados
  status.py         leitura assíncrona de status local
  models.py         estados e dados
  monitor.py        coleta, backoff e reconciliação
  operations.py     locks, confirmação e diário antes do POST
  security.py       allowlist e cooldown
  discord_ui.py     interações privadas e botões
  panel.py          embed, restauração e edição da mensagem
  storage.py        JSON atômico e trava de instância
  logging_setup.py  rotação, sanitização e auditoria
service/            template WinSW
scripts/            preparação, serviço, testes e ZIP
tests/              testes isolados e servidor HTTP local simulado
docs/               tutoriais, segurança e validação
```

Não há servidor web no bot, RCON, console de comandos arbitrários, navegador, framework de IA, gerenciador de processos ou banco de dados. CPU/RAM reais dependem das bibliotecas, rede e sistema; não há promessa de consumo baseada em benchmark não realizado.

## Referências

- [API v2 oficial do Crafty](https://docs.craftycontrol.com/pages/developer-guide/api-reference/v2/) e [OpenAPI](https://docs.craftycontrol.com/pages/developer-guide/api-reference/openapi-spec.yml).
- [Configuração do servidor e timeout de parada](https://docs.craftycontrol.com/pages/user-guide/server-config/minecraft/).
- [discord.py: Client e views persistentes](https://discordpy.readthedocs.io/en/stable/api.html).
- [mcstatus: consulta assíncrona Java](https://mcstatus.readthedocs.io/en/stable/api/basic/).
- [WinSW 2.12: configuração XML](https://github.com/winsw/winsw/blob/v2.12.0/doc/xmlConfigFile.md).

Proejto com **Crafty 4.11.0**; os handlers e o modelo de dados dessa tag foram conferidos. Credenciais não foram fornecidas e a integração real ainda deve ser validada localmente. Veja o contrato em [CRAFTY.md](docs/CRAFTY.md).
