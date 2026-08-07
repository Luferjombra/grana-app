# ADR 0001 — Open Finance (spec 06) adiado por barreira regulatória

**Data:** 2026-08-07
**Status:** aceito

## Contexto

A spec 06 previa conexão bancária via Open Finance usando a Pluggy, atrás da
interface `BankAggregatorProvider`. O produto anunciava três vias de registro
de gasto: manual, foto de recibo (OCR) e conexão bancária.

Ao revisar antes de implementar, o usuário levantou que a empresa não é
instituição financeira. A pesquisa confirmou que isso é bloqueante:

- Só instituições autorizadas pelo BCB podem ser **receptoras de dados** no
  Open Finance ([modelo de participação](https://openfinancebrasil.org.br/modelo-de-participacao/)).
- A Pluggy é autorizada (como Iniciadora de Transação de Pagamento), e seu
  modelo comercial era permitir que empresas não autorizadas consumissem os
  dados via API — o que aparentava resolver o problema.
- **Em março de 2026 o BCB propôs restringir exatamente essa rota**, criando as
  figuras de "instituição integradora" (autorizada) e "entidade parceira" (não
  autorizada), com modelo 1x1x1 e vedação de repasse de dados a terceiros.
- O capital mínimo de ITP subiu de R$ 1 mi para R$ 17 mi; somado a patrimônio,
  a barreira de entrada fica na casa de R$ 30 mi.

Não foi possível confirmar se a resolução já está publicada — a previsão era
abril/maio de 2026 e a matéria mais recente encontrada (28/05/2026) indicava
análise de contribuições em andamento.

## Decisão

Adiar Open Finance. **Não implementar** `PluggyProvider` nem os endpoints de
`/accounts`.

O código já existente fica **dormente**, não removido:
- `app/providers/bank_aggregator/` (interface + `MockProvider`)
- `etl/pluggy_sync.py` (stub)
- tabela `accounts` no schema, com `provider in ('manual','pluggy')`
- `PLUGGY_CLIENT_ID`/`PLUGGY_CLIENT_SECRET` nos `.env.example`

Motivo de manter: o custo de manutenção é zero (nada chama esse código), e
refazer depois custaria o mesmo que custou agora. Se a situação regulatória
mudar, ou se a empresa vier a se estruturar como entidade parceira, a interface
já está no lugar.

## Consequências

- O produto passa a ter **duas** vias de registro, não três.
- **O import de extrato CSV/OFX deixa de ser um extra e vira a única ponte com
  o banco** — sobe de prioridade acessória para essencial.
- A automação do cofrinho via Pluggy ITP, já marcada como fase futura, fica
  ainda mais distante.
- O alerta e a modelagem que dependem de `accounts.last_synced_at` continuam
  sem uso.

## Alternativa considerada e recusada

Conexão direta / screen scraping fora do Open Finance regulado (a Pluggy cita
como permitida sob LGPD). Recusada como base do produto: depende de páginas de
banco que mudam sem aviso, e carrega risco próprio de credencial do usuário.

## A confirmar antes de reabrir

Falar com a Pluggy e com assessoria jurídica sobre o texto final da resolução —
esta ADR se baseia em notícias e na proposta, não no normativo publicado.
