# Validação da entrega

Data: **31/10/2026**. Ambiente de teste: Windows, **CPython 3.13.18 x64** em ambiente isolado. Crafty: **4.11.0**.

## Verificações executadas

| Verificação | Resultado |
|---|---|
| `python -m pytest -q` | **74 testes passaram**, em aproximadamente 3,5 segundos na última execução |
| `ruff check minecraft_bot tests` | Sem erros |
| `python -m compileall -q minecraft_bot` | Sem erros de compilação |
| Parser de PowerShell **5.1.19041.6456** | 10 scripts sem erros sintáticos |
| Template XML WinSW | XML válido; caminhos com espaços e `&` preservados; LocalService e helper de parada conferidos |
| Invocação Python pelos scripts no PowerShell 5.1 | Aspas e verificação de Python x64 conferidas |
| Dependências fixadas | Ambiente sincronizado com `requirements-dev.txt` usando validação de hashes |
| CLI | `python -m minecraft_bot --help` executado |
| WinSW baixado para conferência | SHA-256 conferido contra o valor fixado no script; executável não instalado como serviço |
| Contrato Crafty 4.11.0 | Handlers, serialização, modelo de stats, horários e interface de chaves conferidos nos fontes oficiais da tag |

Os testes emitiram 11 avisos de depreciação internos de `discord.py` sobre o argumento posicional `count` de `re.sub`, sem falhas. Os avisos não foram ocultados. Não indicam vazamento de token nem erro funcional observado nos testes.

## Cobertura funcional dos testes

- Dois IDs autorizados, terceiro usuário rejeitado mesmo sendo administrador, guild/canal incorretos, cooldown individual e respostas privadas de negação.
- Inicialização offline, nenhuma ação se online, concorrência entre dois cliques e ações opostas, reserva durante confirmação.
- Recusa de parada com jogadores, quantidade desconhecida, falha de status local, comando de parada Crafty ausente/incorreto e jogador entrando antes da confirmação final.
- Confirmações de uso único, usuário errado e expiração.
- HTTP real contra um servidor **simulado em loopback**: endpoints exatos, header Bearer, 400 NOT_AUTHORIZED, 401/403/404/429/500, redirecionamento recusado, resposta inválida e rejeição de ações arbitrárias.
- Timeout de transporte simulado, POST aceito com resposta perdida, espera esgotada, cancelamento durante envio e reinício com diário pendente. Sem repetição automática de comando.
- Estados online/offline/indisponível, backoff e recuperação, datas antigas/inválidas/futuras, interpretação UTC/local específica da 4.11.0 e divergência de porta.
- Versão/lista desconhecidas, amostra incompleta, ping falho não tratado como zero e ausência de inferência de pausa.
- Persistência, corrupção e troca de escopo, trava de segunda instância no Windows.
- Criação/edição do painel, edição evitada sem mudanças, restauração após reinício, exclusão de mensagem, resposta de envio perdida e falta de acesso ao histórico sem criar duplicatas.
- Discord desconectado, canal excluído e permissão removida sem envio de ações ao Minecraft.
- Parada pelo arquivo de sinalização, fechamento do bot e ausência de comando para parar Minecraft.
- Redação de tokens, descarte de mensagens arbitrárias de exceções, validação de URL local/TLS e segredo omitido de `repr(Config)`.

Mocks e fixtures representam o contrato conferido, não capturas do servidor do usuário. Os testes HTTP usam `aiohttp.web` apenas durante os testes; o bot em produção não abre servidor web.

## O que não foi validado em integração real

Não foram fornecidos tokens Discord/Crafty, IDs reais, certificado local ou acesso a uma sessão autenticada. Portanto **não foram feitos**:

- Login real do bot Discord ou publicação de painel em sua guild.
- Chamadas à API da sua instalação Crafty.exe.
- Inicialização, salvamento ou parada do seu Minecraft.
- Medição de pausa Vanilla ou benchmark de CPU/RAM em uso real.
- Instalação/registro do serviço no SCM, troca real de ACLs de implantação, reboot ou logout para teste do serviço.
- Teste de uma conexão de jogador no instante entre a consulta e a parada; essa corrida é uma limitação documentada, não resolvida por mocks.

O código e os scripts estão prontos para configuração. Os testes não substituem a validação do ambiente real.

## Roteiro de aceitação local

1. Preencha `.env`, confira o certificado e execute `check` e `doctor` com Minecraft offline. Verifique que ele continua offline.
2. Inicie o bot em primeiro plano e confira o painel, os IDs autorizados e a recusa de uma terceira conta.
3. Com Crafty disponível, clique em Ligar e confira que existe apenas a instância gerenciada pelo Crafty.
4. Entre no jogo; confirme a contagem e a recusa de Desligar. Saia, espere a coleta e teste Cancelar e Confirmar.
5. Verifique o salvamento normal no console do Crafty e a confirmação offline no painel.
6. Reinicie somente o bot e confirme o mesmo ID de mensagem. Exclua a mensagem e confirme uma única recriação.
7. Em um momento apropriado, teste indisponibilidade do Crafty pelo seu procedimento manual: painel cinza, bot ainda online e nenhuma tentativa de abrir o controlador. Restaure e aguarde o backoff.
8. Instale o serviço, encerre o terminal, confirme funcionamento sem janela e pare/reinicie somente o serviço do bot.
9. Teste reboot/logout quando conveniente; considere que o Crafty pode depender de login na configuração existente. Não altere sua inicialização para satisfazer o bot.

Para distribuir novamente, use `scripts/Package.ps1` e revise o ZIP. Os testes podem ser repetidos com `scripts/Test.ps1` após preparação do Python 3.13.
