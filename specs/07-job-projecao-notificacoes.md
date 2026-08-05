# Spec: job de projeção e motor de notificação

## Regras de disparo (já decididas na conversa)
- **Alerta de teto**: gasto acumulado de um bucket/categoria ≥ 95% do respectivo `budget_targets.target_amount` no mês.
- **Alerta de projeção negativa**: projeção linear de fechamento do mês ultrapassa 97% da renda mensal (sobra projetada < 3%).

## Fórmula da projeção
```
ritmo_diario = gasto_total_do_mes_ate_hoje / dias_corridos_no_mes
projecao_fechamento = ritmo_diario * dias_totais_no_mes
dispara_alerta_negativo se projecao_fechamento > (renda_do_mes * 0.97)
```

`gasto_total_do_mes_ate_hoje` = soma de `transactions.amount` onde `type = 'expense'` e `occurred_at` no mês corrente — **só transações já confirmadas** (para OCR, isso é depois do passo de confirmação da spec 05, nunca no momento em que a foto é só enviada).

## Gatilho híbrido (decidido na conversa)

### Evento
Toda vez que uma `transaction` é criada ou atualizada (`entry_method` qualquer):
1. Recalcula o total do bucket/categoria afetado.
2. Se cruzou o limiar de 95%: gera `notification` (type = `budget_ceiling`, severity = `warning`).
3. Recalcula a projeção linear inteira.
4. Se cruzou 97%: gera `notification` (type = `negative_projection`, severity = `danger`).
5. Idempotência: não recriar a mesma notificação se já existe uma não lida do mesmo tipo pro mesmo mês — atualizar a existente em vez de duplicar.

### Cron diário (`etl/projection_recompute.py`, meia-noite local)
- Recalcula a projeção pra todo household com pelo menos uma transação no mês, mesmo sem evento novo (cobre a mudança de `dias_corridos_no_mes`).
- Registra execução em `etl_runs` (job = `projection_recompute`).
- Gera as mesmas notificações que o caminho de evento, se aplicável.

## Outras notificações geradas pelo mesmo motor (do protótipo)
- `goal_hit` (severity = `success`): bucket fechou o mês dentro do teto.
- `reserve_progress` (severity = `info`): reserva de emergência cruzou um marco de 10% (10%, 20%, 30%...).

## Onde roda
Função compartilhada `notifications/engine.py`, chamada tanto pelo hook de evento (dentro do FastAPI, após commit da transaction) quanto pelo script de cron — mesma lógica, dois gatilhos, sem duplicar regra.

## Dependência
Requer `budget_targets` populado (cálculo derivado de `incomes` × `budget_rules`, gerado no início de cada mês ou quando a renda muda) — se não houver `budget_targets` para o mês corrente, o motor deve gerar automaticamente a partir do `budget_rules` do household antes de rodar as checagens.
