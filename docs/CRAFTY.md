# Crafty v2, Minecraft e TLS

## Contrato pesquisado

Consulta realizada em 31/10/2026 na [documentação oficial](https://docs.craftycontrol.com/pages/developer-guide/api-reference/v2/) e na especificação OpenAPI **2.0.1** (versão da especificação).**Crafty 4.11.0**. Também foram conferidos os fontes da [tag oficial v4.11.0](https://gitlab.com/crafty-controller/crafty-4/-/tags/v4.11.0), commit iniciado por `fe65b372`.

O cliente usa exclusivamente:

| Método | Endpoint | Uso |
|---|---|---|
| GET | `/api/v2/servers` | Diagnóstico e descoberta de UUID |
| GET | `/api/v2/servers/{serverID}/stats` | Última estatística coletada |
| POST | `/api/v2/servers/{serverID}/action/start_server` | Pedir inicialização |
| POST | `/api/v2/servers/{serverID}/action/stop_server` | Pedir parada oficial |

Autenticação: `Authorization: Bearer <token>`. Respostas devem ter `status: "ok"`. Ações retornam aceitação, não confirmação do término. Não há POST automático na inicialização do bot, no diagnóstico ou na reconexão.

A especificação contém uma inconsistência de apresentação no schema de `/stats` (campos posicionados junto ao envelope). O [handler oficial de stats](https://gitlab.com/crafty-controller/crafty-4/-/blob/master/app/classes/web/routes/api/servers/server/stats.py) retorna as estatísticas em `data`. O [modelo oficial](https://gitlab.com/crafty-controller/crafty-4/-/blob/master/app/classes/models/server_stats.py) fornece `created`, `started`, `running`, `online`, `max`, `players`, `version`, `waiting_start` e `int_ping_results`; `server_id` é uma relação serializada com os dados do servidor. O parser exige `running` booleano, UUID e porta coerentes e uma data de coleta válida. Formatos incompatíveis não viram valores padrão perigosos.

O contrato foi conferido especificamente no [handler de stats 4.11.0](https://gitlab.com/crafty-controller/crafty-4/-/blob/v4.11.0/app/classes/web/routes/api/servers/server/stats.py), no [modelo 4.11.0](https://gitlab.com/crafty-controller/crafty-4/-/blob/v4.11.0/app/classes/models/server_stats.py), no [serializador](https://gitlab.com/crafty-controller/crafty-4/-/blob/v4.11.0/app/classes/web/base_handler.py) e nas [ações 4.11.0](https://gitlab.com/crafty-controller/crafty-4/-/blob/v4.11.0/app/classes/web/routes/api/servers/server/action.py). **Isso não equivale a testar seu executável com suas credenciais.** Rode `doctor` antes de ativar o serviço. O comando valida o contrato de leitura observado; não testa permissões de POST nem garante versões futuras. Formatos divergentes devem ser analisados com uma amostra sanitizada; não afrouxe as validações para permitir parada com dados desconhecidos.

Uma particularidade confirmada no [servidor 4.11.0](https://gitlab.com/crafty-controller/crafty-4/-/blob/v4.11.0/app/classes/shared/server.py): `started` é UTC sem offset, enquanto `created` do banco usa hora local sem offset. O parser trata esses campos separadamente. `CRAFTY_TIMEZONE` corresponde somente à interpretação de datas locais, não desloca o início UTC.

## Usuário e token de menor privilégio

1. No Crafty, abra **Panel Settings** e a gestão de usuários/cargos.
2. Crie um cargo dedicado, por exemplo `discord-minecraft`. Associe **somente o seu servidor Vanilla**.
3. Conceda apenas a permissão de servidor **COMMANDS**, responsável por ligar/parar/reiniciar. Não conceda Terminal, Files, Config, Backups, Logs, Schedule ou Players.
4. Crie um usuário dedicado `discord-bot`, sem **Superuser**, associado a esse cargo. Não conceda criação de servidores, usuários ou cargos.
5. Edite esse usuário e abra a aba **API Key / API Keys**. Crie uma chave para o bot, selecionando somente a permissão de servidor COMMANDS; deixe acesso total/superuser desligado e permissões globais desligadas. Depois use **Get Token / Obter token** na linha da chave e copie o **token secreto gerado**, não o identificador da chave, para `CRAFTY_TOKEN`. A criação e o botão foram conferidos no [template 4.11.0](https://gitlab.com/crafty-controller/crafty-4/-/blob/v4.11.0/app/frontend/templates/panel/panel_edit_user_apikeys.html).
6. Teste com `list-servers` e `doctor`. Se receber falta de autorização, confira associação ao servidor e a interseção de permissões do usuário/chave. Não use Superuser para contornar uma configuração incorreta.

[Usuários/cargos oficiais](https://docs.craftycontrol.com/pages/user-guide/user-role-config/). A localização da aba também foi conferida no [template oficial de edição de usuário](https://gitlab.com/crafty-controller/crafty-4/-/blob/master/app/frontend/templates/panel/panel_edit_user.html).

**Limite da granularidade:** o Crafty agrupa várias ações em COMMANDS. O token pode ter capacidade mais ampla que os dois endpoints expostos pelo bot; não há uma permissão exclusiva “apenas start e stop” no handler consultado. O código rejeita outras ações, mas proteger o token continua essencial. [Handler de ações e verificação de COMMANDS](https://gitlab.com/crafty-controller/crafty-4/-/blob/master/app/classes/web/routes/api/servers/server/action.py).

O bot usa uma chave fornecida, não salva usuário/senha do Crafty e não faz login automático para obter novos tokens. Revogue e substitua a chave manualmente se ela expirar ou for comprometida.

## Descobrir o UUID do Minecraft

O ID normalmente aparece na URL ao abrir o servidor no Crafty, no parâmetro `id`. Para confirmar via API, execute:

```powershell
.\.venv\Scripts\python.exe -m minecraft_bot list-servers
```

O comando lista somente UUID e nome dos servidores acessíveis. Copie o UUID do seu Vanilla para `CRAFTY_SERVER_ID`. Configure `MC_STATUS_PORT` com a porta desse mesmo servidor e confira que **Server Port** no Crafty corresponde à porta real em `server.properties`. Não aponte o status para outro servidor local. O bot recusa divergência de porta e tipo diferente de `minecraft-java`.

## HTTPS local com certificado autoassinado

Use `https://127.0.0.1:8443` ou `https://localhost:8443`, conforme sua instalação. Não crie port forwarding para a API. O bot aceita apenas loopback e não segue redirecionamentos, evitando encaminhar o token para outro host.

Escolha **uma** das opções:

### Opção A — pin do certificado público (simples para uso local)

1. Localize o certificado **público** realmente utilizado pelo Crafty, na configuração/pasta de certificados da sua instalação, ou exporte-o pelo visualizador de certificado do navegador conectado ao Crafty local. Não exporte nem copie a chave privada.
2. Confirme que o certificado veio dessa instalação, não de uma origem desconhecida.
3. Calcule o fingerprint sobre o certificado DER usando o helper (aceita PEM ou DER):

```powershell
.\.venv\Scripts\python.exe -m minecraft_bot cert-fingerprint --file 'C:\caminho\certificado-publico.pem'
```

4. Copie os 64 caracteres hexadecimais para `CRAFTY_CERT_SHA256` e deixe `CRAFTY_CA_FILE` vazio.

O pin verifica os bytes exatos do certificado durante a conexão TLS; é uma confiança explícita nesse certificado, em vez da validação normal de CA/hostname. Não é `ssl=False`. Quando o Crafty trocar ou regenerar seu certificado, a conexão falhará até você verificar e atualizar o pin. Não use o hash do arquivo PEM em texto; o helper converte para DER corretamente.

### Opção B — CA confiável

Coloque a CA/PEM em `certs` e preencha `CRAFTY_CA_FILE=certs/crafty-ca.pem`. Deixe o fingerprint vazio. O certificado servido deve ser válido para o hostname/IP usado em `CRAFTY_URL` e ter cadeia confiável. Um autoassinado pode servir como raiz explicitamente confiável, mas ainda precisa satisfazer as regras de hostname e certificado do Python/OpenSSL.

Se os dois campos estiverem vazios, vale a confiança padrão do Python/Windows; o autoassinado padrão do Crafty normalmente falhará. Não há opção para desabilitar verificação de TLS. [Acesso HTTPS e certificado padrão do Crafty](https://docs.craftycontrol.com/pages/getting-started/access/).

## Configuração Minecraft e parada

Mantenha suas opções atuais de memória, distâncias, limite de dois jogadores, whitelist, `online-mode=true` e `pause-when-empty-seconds=60`. O projeto não edita `server.properties` nem o comando Java.

Para status local, `enable-status=true` deve estar ativo (já é comum no Vanilla). Não é necessário habilitar Query nem RCON. `hide-online-players=true` pode ocultar nomes; o painel não inventa a lista. O status passa pela porta normal do jogo, restrito a loopback do lado do cliente do bot. Nenhuma porta adicional é aberta.

Confira manualmente no Crafty:

- **Auto Start desligado**, conforme sua preferência.
- **Stop Command = `stop`**, adequado ao Vanilla. O bot recusa a parada se esse campo estiver ausente ou diferente.
- **Shutdown Timeout** suficiente para salvar o mundo (por exemplo, 180 segundos, ajustado ao tamanho real do mundo e ao disco). Não o reduza para acelerar a confirmação do bot.

O timeout do Crafty é independente de `STOP_TIMEOUT_SECONDS`. O primeiro pode levar o próprio Crafty a terminar um processo travado; o segundo apenas encerra a espera interativa do bot e mantém o diário. Por isso é necessário conferir a configuração existente. O bot não envia `kill_server`, não força término e não altera configurações automaticamente. Faça backups pelo seu procedimento usual, fora deste bot.

Uma estatística recente com ping bem-sucedido alimenta o painel; para parar, exige-se também uma nova consulta de status local imediatamente antes do POST. Contagem positiva do Crafty veta a parada mesmo quando o status local já mostra zero, até a próxima coleta. Isso privilegia recusar uma parada temporariamente a desligar com informação conflitante.

O bot não altera whitelist, firewall ou propriedades para impedir conexões: isso não forneceria uma transação atômica segura e poderia deixar vocês bloqueados após uma falha. Os dois usuários devem evitar entrar enquanto a confirmação/parada estiver em andamento.
