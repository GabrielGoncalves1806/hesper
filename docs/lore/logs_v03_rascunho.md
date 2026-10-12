# LOGs do v0.3 (texto do gerente · APROVADO pelo dono)

Os 3 LOGs do v0.1 ficam na caverna. Estes 4 são novos e ficam nos destroços da superfície.
Eles não resolvem o mistério do gelo: só deixam ele maior.

O dono aprovou sem ler (quer se surpreender jogando). O texto valendo é o do `game/config.py` (`LOGS`).
O número exibido no jogo segue a **cronologia da história** (`LOG_DAYS` / `LOG_ORDER`), não a ordem de achar:
a coluna "Exibido" abaixo é o que o jogador vê; "Índice" é a posição em `LOGS` (o save guarda o índice).

| Índice | Exibido | Dia | Onde | Texto |
|---|---|---|---|---|
| 3 | LOG 05 | 188 | Nave de carga (a mais perto) | "Dia 188. Cargueira VÉSPER-7, manifesto de retorno. Carga: 12 toneladas de gelo de núcleo, lacrado em contêiner frio, prioridade da diretoria. Motivo do retorno: tripulação pediu pra não levar. Pedido negado." |
| 4 | LOG 04 | 140 | Módulo da colônia (média distância) | "Dia 140. A Dra. Ilves colocou uma amostra do gelo do fundo da cratera no microscópio e ficou em silêncio a tarde inteira. À noite ela trancou o laboratório e levou a chave. Disse só: 'cresce quando ninguém olha'." |
| 5 | LOG 02 | 41 | Sonda (longe) | "Dia 41. Sonda de mapeamento S-3. Leitura térmica anômala abaixo da cratera principal: o calor sobe sozinho, sem fonte conhecida. Recomendação automática: não perfurar. Status da recomendação: ignorada." |
| 6 | LOG 07 | 230 | Módulo da colônia (o mais longe) | "Dia 230. Última mensagem da Colônia Hesper. Desligamos os derretedores. Todos. Se alguém achar isto: o planeta não está morto. Ele está esperando. Não acorde o gelo." |

Notas:
- **VÉSPER-7** é o nome da cargueira (eco de "Hesper", que é Vésper em grego). Se preferir outro nome, troca.
- Ajustes do gerente na aprovação: "Dia 188." e "Dia 41." na frente da VÉSPER-7 e da sonda (todo LOG tem dia), e o
  gelo do dia 140 vem do "fundo da cratera" (o LOG do dia 212 diz que só no dia seguinte descem pro nível 2).
- Os 3 da caverna (índices 0, 1, 2 · dias 3, 97, 212) são exibidos como LOG 01, 03 e 06.
- O LOG 07 é o mais forte, por isso fica no destroço mais longe: a recompensa de explorar até a borda.
- O tom continua o do v0.1: frases curtas, diário de bordo, sem explicar demais.
