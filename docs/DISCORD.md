# Configurar Discord

## Aplicação e token

1. Entre no [Discord Developer Portal](https://discord.com/developers/applications) e use **New Application**. Escolha um nome, como `Minecraft Survival`.
2. Abra a área **Bot**. Aplicações novas já possuem um usuário bot; se houver um botão para criá-lo, use-o.
3. Em **Token**, use **Reset Token** e guarde o token imediatamente. Cole em `DISCORD_TOKEN` no `.env`. Nunca use seu token de usuário Discord.
4. Deixe os intents privilegiados **Presence**, **Server Members** e **Message Content** desligados. O projeto só precisa do intent normal `guilds`.
5. O bot pode ser privado: desative **Public Bot** se disponível. Em Installation, use instalação na guild. Não precisa de instalação em conta pessoal.
6. Deixe **Interactions Endpoint URL** vazio: este projeto recebe botões pelo Gateway, não por um servidor HTTP.

[Fluxo oficial de criação e token](https://docs.discord.com/developers/quick-start/getting-started).

## Convidar com permissões mínimas

Em **OAuth2 → URL Generator**, selecione o escopo `bot`. Conceda somente:

- **View Channels** / Ver canais.
- **Send Messages** / Enviar mensagens.
- **Embed Links** / Inserir links.
- **Read Message History** / Ler histórico de mensagens.

Não precisa de Administrator, Manage Messages, Manage Channels, Manage Guild, voz ou webhooks. Não existem comandos slash neste projeto, portanto `applications.commands` não é necessário. Abra a URL gerada e selecione sua guild. Você precisa de permissão para instalar o bot; isso não lhe concede automaticamente acesso aos controles no código.

Crie um canal de texto comum, como `#minecraft-controle`, preferencialmente dedicado. Garanta as quatro permissões ao bot **nas sobrescritas do canal**, não apenas no cargo global. Você pode limitar a visualização a vocês dois, mas a segurança dos controles sempre é feita por ID no backend.

## IDs: você, amigo, guild e canal

No Discord, abra **Configurações do usuário → Avançado → Modo desenvolvedor**.

1. Clique com o botão direito no seu usuário e escolha **Copiar ID do usuário** → `OWNER_DISCORD_ID`.
2. Faça o mesmo para seu amigo → `FRIEND_DISCORD_ID`.
3. Clique com o botão direito no ícone do servidor Discord → **Copiar ID do servidor** → `DISCORD_GUILD_ID`.
4. Clique com o botão direito no canal de texto → **Copiar ID do canal** → `DISCORD_CHANNEL_ID`.

Copie apenas os números, sem `<@...>`, `#` ou aspas extras. Não coloque nomes de usuário, IDs de cargos, ID da aplicação nem ID do servidor Minecraft nesses campos.

## Criar e conferir o painel

Execute o bot depois de preencher o `.env`. Ele publica automaticamente uma única mensagem. Não há comando de criação manual. A mensagem mantém os handlers após o reinício graças aos `custom_id` fixos e à restauração de `data/state.json`.

Verifique localmente:

1. Com Minecraft offline, abrir o bot não deve iniciar nada.
2. Use Atualizar com cada ID autorizado.
3. Use uma terceira conta, inclusive uma conta administradora, e confira a resposta privada de falta de permissão quando os botões estiverem ativos.
4. Com um jogador conectado, Desligar deve ser recusado sem enviar um comando de parada.
5. Sem jogadores, Desligar pede confirmação privada e reconsulta os dados antes de enviar a parada.
6. Reinicie só o bot: a mesma mensagem deve permanecer.

Quando um botão está visualmente desabilitado, o Discord não envia a interação. Para toda interação que chega, o backend valida ID, guild, canal e mensagem. Confirmações também validam o usuário que as criou.

Sem conexão com Discord, o bot não recebe novos cliques. Uma operação já enviada ao Crafty pode continuar; o diário conserva essa informação para a reconexão. Ephemerals têm vida limitada no Discord; operações foram limitadas a no máximo 10 minutos para permanecer dentro da janela usual do token de interação.

Se o token vazar, redefina-o no portal, atualize `.env` e reinicie somente o serviço do bot. Nunca publique o arquivo `.env`, logs completos sem revisão ou prints que mostrem o token.
