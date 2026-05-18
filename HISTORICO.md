# Historico de Commits Relevantes - alerta-vendas

> Ordem cronologica dos principais commits. Para detalhes, ver git log.

## Sessao atual (mais recentes primeiro)

| Commit | Mensagem | O que faz |
|--------|----------|-----------|
| df3d98b | chore: atualiza dados [skip ci] | Auto-commit do workflow (snapshot 23:38) |
| 08f6813 | feat: HORA_INICIO 10h e catch-up de horas perdidas quando cron falha | Acerta horario inicial e adiciona logica de catch-up |
| b2bb75b | backup: alerta_vendas.py antes de mudar HORA_INICIO | Versao backup v10 20260516 |
| b7022a3 | Update historico.json | Atualizacao manual do historico |
| (varios) | chore: atualiza dados [skip ci] | Auto-commits horarios do workflow |

## Resumo do que cada um deveria saber

- O projeto **funciona** atualmente e roda via GitHub Actions a cada 30min entre 10h e 22h BRT
- Monitora 3 lojas: Rio Sul (1), Barra Shopping (3), NorteShopping (4)
- Sistema de premios por loja com perda por alerta (ciclo de 7 dias, premio inicial R$1500, perda R$50 por alerta)
- Pages publicado em https://leonardochor-hash.github.io/alerta-vendas/alerta-vendas2/

## Atualizacao 2026-05-17 22:30

- Documentacao adicionada (CONTEXTO.md + HISTORICO.md) para retomada de contexto
- Estado atual dos contadores: alerta_1=2, alerta_3=6, alerta_4=5 (17/05/2026 19h)
- Saldos: RS R$1400, BS R$800, NS R$1050
