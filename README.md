# alerta-vendas

Monitor de inatividade de vendas das lojas Moombox. Roda a cada 30 minutos e envia alerta por email se uma loja nao realizou nenhuma venda nos ultimos 30 minutos.

## Funcionalidades

- Verifica vendas dos ultimos 30 minutos para cada loja (Rio Sul, Barra Shopping, NorteShopping)
- Se nao houver venda: envia email de alerta com:
  - Nome da loja
  - Tempo total sem venda (30min, 1h, 1h30min...)
  - Numero do alerta consecutivo (quanto maior, mais urgente)
  - Instrucao de acao para a gerente
- Se houver venda: nenhum email enviado, contador resetado
- Alertas separados por loja

## Como configurar

### Secrets necessarios no GitHub:
| Secret | Valor |
|---|---|
| `GMAIL_APP_PASSWORD` | Senha de app do Google (16 caracteres) |

### Variaveis fixas no workflow:
| Variavel | Valor |
|---|---|
| `EMAIL_REMETENTE` | cap00leonardo@gmail.com |
| `EMAIL_DESTINATARIO` | leonardochor@gmail.com |

## Como testar manualmente

1. Va em **Actions** > **Alerta Inatividade Vendas**
2. Clique em **Run workflow**
3. Preencha os campos opcionais:
   - **hora_simulada**: ex: `13`
   - **data_simulada**: ex: `14/05/2026`
   - **min_simulada**: ex: `30`
4. Clique em **Run workflow**

## Logica de alertas consecutivos

| Alerta | Tempo sem venda | Instrucao |
|---|---|---|
| #1 | 30 min | Verifique se o terminal esta ligado |
| #2 | 1h | Confira se ha clientes sendo atendidos |
| #3 | 1h30 | Verifique se o sistema de pagamento funciona |
| #4 | 2h | Entre em contato com a equipe imediatamente |
| #5+ | 2h30+ | Verifique se ha problema tecnico |

## Horario de funcionamento

Das **10h00 as 22h00** (horario de Brasilia). Fora desse horario nenhum alerta e enviado.
