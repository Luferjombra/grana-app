# Spec: envio de push notifications

## Registro de token de dispositivo

Nova tabela (adicionar à migration `0009` ou criar `0010_push_tokens.sql`):

```sql
create table push_tokens (
  id          bigserial primary key,
  user_id     uuid not null references profiles(id) on delete cascade,
  token       text not null,
  platform    text not null check (platform in ('ios','android')),
  created_at  timestamptz not null default now(),
  unique (user_id, token)
);
```

RLS: família B (user_id).

## Fluxo de registro
1. No primeiro login, o app pede permissão de notificação (Expo Notifications).
2. Se concedida, o app obtém o Expo Push Token e envia pro backend (`POST /push-tokens`).
3. Backend faz upsert em `push_tokens`.

## Envio
Sempre que o motor de notificação (spec 07) cria uma `notification` com `severity` em `warning` ou `danger`, dispara push em paralelo:

```python
async def send_push(user_id: str, title: str, message: str):
    tokens = await get_push_tokens(user_id)
    if not tokens:
        return
    await expo_push_client.send(tokens, title=title, body=message)
```

- `severity = info` ou `success`: só in-app, sem push (evita fadiga de notificação nos alertas mais informativos, reserva o push pra o que exige atenção real — teto estourando e projeção negativa).
- Falha de envio (token inválido/expirado): remover o token da tabela, não travar o fluxo do resto da notificação.

## Dependência
Requer credenciais de push configuradas no Expo/EAS (task #5) — sem isso, o backend deve logar aviso e seguir só com a notificação in-app, sem quebrar o restante do fluxo.

## Fora de escopo
Preferências de notificação por tipo (usuário desligar só o alerta de teto, por exemplo) — não discutido ainda, registrar como ideia de backlog.
