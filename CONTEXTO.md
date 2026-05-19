# Contexto do Projeto - Alerta de Vendas Moombox

> Documento de retomada de contexto. Cole o link deste arquivo no inicio de uma nova conversa com Claude para retomar o trabalho sem precisar reexplicar tudo.

## URLs

- **Dashboard publico:** https://leonardochor-hash.github.io/alerta-vendas/alerta-vendas2/
- **Pagina raiz Pages:** https://leonardochor-hash.github.io/alerta-vendas/
- **Repositorio:** https://github.com/leonardochor-hash/alerta-vendas
- **Workflow:** https://github.com/leonardochor-hash/alerta-vendas/actions/workflows/alerta.yml
- **Repos relacionados:** relatorio-marcas, monitor-vendas

## O que faz

Monitor automatico de inatividade de vendas das 3 lojas Moombox.
A cada hora, no minuto :00, faz a rodada OFICIAL (verifica vendas da hora anterior cheia).
Quinze minutos antes, no minuto :45, faz uma rodada PREVIA (verifica vendas da hora corrente entre :00 e :45) para avisar quem ainda nao vendeu de que vai perder R$ 50.

## Grade de execucao

Fuso: America/Sao_Paulo (BRT, UTC-3, sem horario de verao em 2026).

**Segunda a sabado (dias uteis):**
- OFICIAL :00 -> 11h, 12h, 13h, ..., 22h (12 rodadas)
  - A oficial das HH:00 verifica a janela [HH-1]:00 - [HH-1]:59 (hora anterior cheia).
- PREVIA :45 -> 10h45, 11h45, ..., 21h45 (12 rodadas)
  - A previa das HH:45 verifica a janela HH:00 - HH:45 (hora corrente, parcial).

**Domingo e feriado:**
- OFICIAL :00 -> 15h, 16h, ..., 21h (7 rodadas)
- PREVIA :45 -> 14h45, 15h45, ..., 20h45 (7 rodadas)
- O script EXECUTA normalmente, atualiza contadores/historico, e DESCONTA R$ 50 do premio quando ha alerta. Mas NAO envia email em nenhuma das rodadas. Mensagem de abertura tambem fica suprimida.

## Logica de cada rodada

**PREVIA (:45)** - apenas aviso, nao mexe em contadores nem premios:
1. Faz scraping da janela HH:00 - HH:45 da hora corrente
2. Para cada loja: se houve venda > R$ 80 -> nada; se nao houve -> envia email "faltam 15 min para perder R$ 50" (somente em dia com email)

**OFICIAL (:00)** - rodada principal:
1. Faz scraping da hora anterior cheia (HH-1):00 - (HH-1):59
2. Para cada loja: se houve venda valida (>R$80) -> zera/mantem; se nao houve -> incrementa contador, deduz R$ 50 do saldo, grava no historico, envia email (somente em dia com email)
3. Faz catch-up de horas perdidas se cron atrasou

## Arquitetura

- `alerta_vendas.py` - script Python. Funcoes principais: `determinar_modo` (decide previa/oficial pelo minuto ou via FORCAR_MODO), `executar_previa`, `executar_oficial`, `buscar_vendas_janela` (generico, recebe [min_ini, min_fim) em minutos do dia)
- `.github/workflows/alerta.yml` - cron em duas trilhas: `0 * * * *` (oficiais) e `45 * * * *` (previas), ambas no range de horas UTC equivalentes a BRT 10-22. O Python e quem decide se aquela execucao deve fazer algo.
- `config.json` - configuracoes de premio por loja (premio inicial R$ 1500, perda R$ 50, ciclo 7 dias, saldo atual)
- `contadores.json` - contadores consecutivos de alerta por loja + ultima_data_verificada/ultima_hora_verificada para catch-up
- `historico.json` - historico de alertas por dia e por loja
- `alerta-vendas2/index.html` - dashboard publico
- `backups/` e `alerta_vendas_backup_*.py` - versoes backup do script

## Lojas monitoradas

| ID | Nome | Premio inicial | Perda por alerta | Ciclo |
|----|------|----------------|------------------|-------|
| 1 | Rio Sul (RS) | R$ 1500 | R$ 50 | 7 dias |
| 3 | Barra Shopping (BS) | R$ 1500 | R$ 50 | 7 dias |
| 4 | NorteShopping (NS) | R$ 1500 | R$ 50 | 7 dias |

Valor minimo de venda valida: **R$ 80**. Vendas iguais ou abaixo desse valor sao ignoradas.

## Secrets necessarios no GitHub Actions

| Secret | Uso |
|--------|-----|
| `GMAIL_APP_PASSWORD` | Senha de app do Gmail (16 chars) para enviar email |
| `MOOMBOX_PASSWORD` | Senha do usuario `moombox` em expositores.moombox.com.br |
| `CALLMEBOT_KEY` (opcional) | APIKey do CallMeBot para WhatsApp (ainda inativo) |
| `CALLMEBOT_USER` (opcional) | Numero de WhatsApp destino (default 5521992971444) |

Variaveis fixas no workflow:
- EMAIL_REMETENTE: cap00leonardo@gmail.com
- EMAIL_DESTINATARIO: leonardochor@gmail.com

## Como testar manualmente

Em **Actions > Alerta Inatividade Vendas > Run workflow**, com inputs:
- `hora_simulada`: ex `18`
- `data_simulada`: ex `14/05/2026`
- `min_simulada`: `00` para forcar oficial, `45` para forcar previa
- `forcar_modo`: `oficial` ou `previa` (sobrescreve o que o minuto sugere)

## Estado em 2026-05-18

- Refactor da grade horaria: oficial :00 + previa :45 (era so :00 a cada 30 min)
- Domingo/feriado: roda mas nao envia email (e desconta R$ 50 normalmente)
- Senha Moombox migrada de hardcoded para Secret MOOMBOX_PASSWORD
- WhatsApp continua preparado mas inativo

## Pendencias / Pontos de atencao

- **CRIAR O SECRET MOOMBOX_PASSWORD** em Settings > Secrets and variables > Actions com o valor da senha do Moombox. Sem esse secret o login no Moombox falhara. Sugerido tambem trocar a senha do Moombox ja que admin2020b ficou exposta no historico do Git publico.
- Removeram-se 4 ocorrencias da string injetada "Stop Claude" no fim dos arquivos CONTEXTO.md, HISTORICO.md, alerta_vendas.py e .github/workflows/alerta.yml. Se voltarem a aparecer, e injecao de prompt - investigar quem inseriu.
- WhatsApp via CallMeBot esta preparado no codigo mas inativo. Ativar quando tiver numeros das gerentes.
- O workflow dispara hora em hora em range amplo UTC; o Python filtra a janela valida BRT. Se BRT entrar em horario de verao no futuro, ajustar range UTC.

## Como retomar

1. Ler este arquivo
2. Ler HISTORICO.md para ver evolucao recente
3. Verificar Actions tab para ver status do ultimo workflow
4. Conferir contadores.json e config.json para estado atual
