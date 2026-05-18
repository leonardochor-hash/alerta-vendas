# Contexto do Projeto - Alerta de Vendas Moombox

> Documento de retomada de contexto. Cole o link deste arquivo no inicio de uma nova conversa com Claude para retomar o trabalho sem precisar reexplicar tudo.

## URLs

- **Dashboard publico:** https://leonardochor-hash.github.io/alerta-vendas/alerta-vendas2/
- **Pagina raiz Pages:** https://leonardochor-hash.github.io/alerta-vendas/
- **Repositorio:** https://github.com/leonardochor-hash/alerta-vendas
- **Workflow:** https://github.com/leonardochor-hash/alerta-vendas/actions/workflows/alerta.yml
- **Repos relacionados:** relatorio-marcas, monitor-vendas

## O que faz

Monitor automatico de inatividade de vendas das 3 lojas Moombox. Roda a cada 30 minutos entre 10h e 22h (BRT) via GitHub Actions e envia email se a loja nao realizou nenhuma venda nos ultimos 30 minutos.

## Arquitetura

GitHub Pages estatico + GitHub Actions agendado.

- `alerta_vendas.py` - script Python que faz login em expositores.moombox.com.br, verifica vendas dos ultimos 30min de cada loja, envia email (Gmail SMTP) se ficou inativa, atualiza contadores, historico e config (saldos de premio)
- `.github/workflows/alerta.yml` - roda a cada 30min entre 10h-22h BRT (cron + condicional por hora)
- `config.json` - configuracoes do programa de premios por loja (premio inicial, perda por alerta, ciclo, saldo atual)
- `contadores.json` - contadores consecutivos de alerta por loja + ultima data/hora verificada
- `historico.json` - historico de alertas por dia e por loja (horarios em que cada loja recebeu alerta)
- `backups/` e `alerta_vendas_backup_*.py` - versoes backup do script
- `index.html` (raiz) - pagina simples de status
- `alerta-vendas2/index.html` - dashboard publico com cards de premios, contadores, historico

## Lojas monitoradas

| ID | Nome | Premio inicial | Perda por alerta | Ciclo |
|----|------|----------------|------------------|-------|
| 1  | Rio Sul (RS) | R$ 1500 | R$ 50 | 7 dias |
| 3  | Barra Shopping (BS) | R$ 1500 | R$ 50 | 7 dias |
| 4  | NorteShopping (NS) | R$ 1500 | R$ 50 | 7 dias |

Ciclo atual inicia em 15/05/2026.

## Secrets necessarios no GitHub Actions

| Secret | Uso |
|--------|-----|
| `GMAIL_APP_PASSWORD` (EMAIL_PASS) | Senha de app do Gmail (16 caracteres) para enviar email |

Variaveis fixas no workflow:
- EMAIL_REMETENTE: cap00leonardo@gmail.com
- EMAIL_DESTINATARIO: leonardochor@gmail.com

## Logica resumida

1. Para cada loja (1, 3, 4):
   - Faz scraping da pagina de vendas dos ultimos 30min
   - Se houver venda: zera contador, nada acontece
   - Se NAO houver venda: incrementa contador, envia email com tempo total inativo, deduz R$50 do saldo atual de premio
2. Atualiza `contadores.json`, `historico.json`, `config.json`
3. Faz commit auto "chore: atualiza dados [skip ci]"

## Estado atual (2026-05-17)

- Contadores: alerta_1=2, alerta_3=6, alerta_4=5 (ultima verificacao 17/05/2026 19h)
- Saldos premio: RS R$ 1.400, BS R$ 800, NS R$ 1.050
- Premio inicial 1500 - perdas acumuladas (2, 14, 9 alertas no ciclo)

## Pendencias / Pontos de atencao

- **CREDENCIAL EXPOSTA**: `alerta_vendas.py` linha 12 contem `SENHA = "admin2020b"` hardcoded - deveria estar em GitHub Secret
- WhatsApp via CallMeBot esta no codigo (variaveis WHATSAPP_NUMERO, WHATSAPP_APIKEY) mas parece nao estar ativado
- Workflow agendado com cron tem latencia variavel; commit b2bb75b adicionou catch-up de horas perdidas

## Como retomar

1. Ler este arquivo
2. Ler HISTORICO.md para ver evolucao recente
3. Verificar Actions tab para ver status do ultimo workflow
4. Conferir contadores.json e config.json para estado atual
