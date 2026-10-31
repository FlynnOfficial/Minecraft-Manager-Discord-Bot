# Decisões de segurança e limites

## Fronteiras de controle

- Autorização usa dois IDs exatos. Permissões Discord, cargos e propriedade da guild nunca concedem acesso implícito.
- Botões principais verificam também guild, canal e mensagem ativa. A confirmação verifica novamente localização e o usuário que a pediu, além de um ticket de uso único com expiração.
- Somente dois caminhos POST são permitidos. Não há métodos de terminal/console, RCON, shell, execução de Java ou gerenciamento de processos.
- O cliente HTTP reutiliza uma sessão limitada a duas conexões, exige TLS, não usa proxies herdados e não segue redirects.
- Campos ausentes, formatos incorretos, dados antigos, falha de ping e contagens desconhecidas não viram zero por conveniência.
- O serviço lê código e segredos, mas só grava no estado e nos logs. Administradores Windows podem acessar esses arquivos; isso não é evitável com uma aplicação local controlada por eles.

## Parada e corrida de conexão

A confirmação só é emitida após uma consulta ao Crafty e ao status local. Quando confirmada, o bot repete as consultas sob o lock de operação. Qualquer contagem positiva em uma dessas fontes bloqueia a parada; status local sem contagem bloqueia também. O comando de parada configurado no Crafty deve ser exatamente `stop`.

Há uma janela inevitável entre a resposta do status e a execução de `stop_server` pelo Crafty. Além disso, o status Vanilla pode refletir uma amostra recente, não uma transação em tempo real. Uma conexão nesse intervalo pode resultar em um jogador sendo desconectado pela parada. O salvamento continua sendo o fluxo oficial do Vanilla/Crafty, mas a regra de “nenhum jogador” não pode ser garantida matematicamente até o último instante por estas APIs.

Não alteramos whitelist: whitelist habilitada não impede um usuário já autorizado de entrar, e removê-los temporariamente exigiria restauração persistente após falhas. Não usamos firewall, desativação de rede ou alteração de propriedades: introduziriam privilégios elevados e risco de deixar o servidor inacessível. RCON `list` reduziria uma parte da defasagem, mas ainda não criaria atomicidade e adicionaria credenciais/superfície de acesso. Foi escolhido status local somente de leitura, sem portas extras.

Se você exigir garantia absoluta contra entrada nesse intervalo, o desligamento pelo Discord deve permanecer sem uso; seria necessário um mecanismo atômico no servidor/controlador ou mudar a arquitetura. Para dois usuários, coordenar que ninguém entre durante a confirmação é a mitigação operacional simples.

## Concorrência e durabilidade

O lock assíncrono de operação serializa início/parada. Uma confirmação pendente reserva o controle por até 30 segundos. Duplos cliques, confirmações reaproveitadas e ações opostas são recusados. O monitor e as interações também compartilham uma trava de leitura; o painel possui sua própria trava de publicação.

A intenção é gravada em JSON temporário, seguida de flush/fsync e substituição atômica, **antes** do POST. Em cancelamento, reboot, falha HTTP ou resposta perdida, a intenção continua pendente. Não se tenta obter “exactly once” por repetição de um endpoint sem chave de idempotência. Uma resposta de falha inequívoca, como autenticação negada, libera a intenção; falhas ambíguas preservam-na.

A reconciliação só conclui com dados posteriores ao pedido, estado alvo e status local coerente. Timeout não declara sucesso nem mata processos. O bot continua monitorando, bloqueia novas operações e oferece um comando local de limpeza após inspeção humana. A trava de instância é liberada pelo Windows mesmo se Python cair.

Não há garantia de coordenação com cliques manuais no Crafty, outro cliente da API ou outra cópia do bot em outro diretório. Use apenas esta instalação para os controles Discord. A validação de estado reduz conflitos, mas não cria um lock distribuído no Crafty.

## Dados exibidos

- Zero jogadores não significa pausa. Nenhum estado “Pausado” é exibido sem fonte confiável; a API e o status utilizados não fornecem um indicador inequívoco de pausa.
- `running=true` confirma processo conhecido pelo Crafty; a resposta local confirma que o Minecraft responde ao protocolo de status. Não prova que todo tick futuro estará saudável.
- Crafty inacessível deixa estado Minecraft indisponível, nunca automaticamente offline.
- Status e versão vêm de consulta local ou estatística Crafty válida. Nomes podem ser amostrados/ocultos; isso é sinalizado, sem completar a lista artificialmente.
- Sem fonte confiável para uma transição manual, o painel não inventa “iniciando/desligando”. Esses estados têm evidência do pedido local pendente ou de `waiting_start`.

## Credenciais e auditoria

Não há credenciais reais nos arquivos distribuídos. `.env`, certificados, estado e logs são excluídos do ZIP por construção. As dependências têm versões e hashes fixados; WinSW também tem hash fixado. Na alteração de dependências, confira novas versões, gere locks e execute testes.

O logger registra eventos, IDs e códigos de erro fixos, sanitiza os tokens configurados e padrões Bearer e descarta detalhes arbitrários de exceções. Corpos HTTP, cabeçalhos e variáveis de ambiente nunca são despejados nos logs. Isso reduz exposição acidental, mas revise qualquer arquivo antes de compartilhá-lo.

A autorização Discord não protege contra alguém que já possua seu token Crafty, token do bot ou controle administrativo do Windows. Revogue credenciais vazadas. O privilégio COMMANDS do Crafty é mais amplo que os dois controles da interface; guarde a chave com o mesmo cuidado que uma credencial de administração do servidor.
