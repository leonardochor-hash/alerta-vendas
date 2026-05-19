# Historico de Commits Relevantes - alerta-vendas

> Ordem cronologica dos principais commits. Para detalhes, ver git log.

## Sessao 2026-05-18

| Commit | Mensagem | O que faz |
|--------|----------|-----------|
| (CONTEXTO) | docs(CONTEXTO): atualiza grade :00/:45, regras dom/feriado, Secret MOOMBOX_PASSWORD | Documenta nova grade horaria, modo PREVIA vs OFICIAL, regras dom/feriado, e o novo Secret |
| bd7d7b2 | feat: previa :45, oficial :00, dom/feriado sem email, remove senha hardcoded (MOOMBOX_PASSWORD) | Refatora script: separa rodada PREVIA (minuto :45, janela HH:00-HH:45 da hora corrente, so envia aviso "faltam 15 min para perder R$ 50") da OFICIAL (minuto :00, hora anterior cheia, com email + desconto + contador + historico). Dom/feriado roda mas nao envia email (mantem desconto). Senha do Moombox passa a ler de os.environ.get('MOOMBOX_PASSWORD'). Remove o antigo aviso de encerramento generico. |
| 16fbac8 | feat(workflow): nova grade :00 (oficial) e :45 (previa) - dom/feriado sem email | Workflow passa a disparar tanto em :00 quanto em :45 no range UTC suficiente. Adiciona env MOOMBOX_PASSWORD e input forcar_modo no workflow_dispatch. |

## Sessao anterior (mais recentes primeiro)

| Commit | Mensagem | O que faz |
|--------|----------|-----------|
| df3d98b | chore: atualiza dados [skip ci] | Auto-commit do workflow (snapshot 23:38) |
| 08f6813 | feat: HORA_INICIO 10h e catch-up de horas perdidas quando cron falha | Acerta horario inicial e adiciona logica de catch-up |
| b2bb75b | backup: alerta_vendas.py antes de mudar HORA_INICIO | Versao backup v10 20260516 |
| b7022a3 | Update historico.json | Atualizacao manual do historico |

## Resumo geral

- O projeto monitora 3 lojas (Rio Sul, Barra Shopping, NorteShopping) e roda via GitHub Actions.
- Cada hora, no minuto :00, faz a OFICIAL: verifica a hora anterior cheia (HH-1:00 a HH-1:59), descontando R$ 50 por loja sem venda valida (>R$80), incrementando contador, gravando historico e enviando email (exceto dom/feriado).
- Quinze minutos antes, no minuto :45, faz a PREVIA: verifica HH:00 - HH:45 e, se a loja ainda nao vendeu, manda email "faltam 15 min para perder R$ 50" (exceto dom/feriado).
- Dom/feriado: janela 14h-21h (previa 14:45-20:45, oficial 15:00-21:00), roda e desconta normalmente, mas nao envia email.
- Pages publicado em https://leonardochor-hash.github.io/alerta-vendas/alerta-vendas2/

## Atualizacao 2026-05-18

- Reescrita da grade horaria: agora ha dois modos PREVIA/OFICIAL com cron separado.
- Migrada a senha do Moombox para o Secret `MOOMBOX_PASSWORD` (era hardcoded como `admin2020b` - RECOMENDADO TROCAR no Moombox).
- Domingo e feriados nacionais (2026) agora sao silenciosos por email mas mantem desconto de premio.
