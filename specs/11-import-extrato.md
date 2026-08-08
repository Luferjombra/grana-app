# Spec: import de extrato (CSV/OFX)

Com Open Finance adiado (`docs/adr/0001-open-finance-adiado.md`), este import
deixou de ser conveniência e passou a ser **a única ponte com o banco**.

## Fluxo em duas etapas

O import nunca grava direto: o usuário revisa antes.

1. `POST /transactions/import` — multipart com o arquivo. **Não persiste nada.**
   Devolve o preview: linhas lidas, tipo inferido, e marcação do que parece
   duplicado.
2. `POST /transactions/import/confirm` — recebe as linhas que o usuário
   confirmou, cada uma **com categoria**, e cria as transactions em lote.

Preview é **stateless**: o cliente devolve as linhas na confirmação, em vez de
o servidor guardar o lote numa tabela temporária. Evita uma migration e um
job de limpeza de lotes abandonados; o backend revalida tudo na confirmação,
então não há risco em confiar no que volta.

## Formatos

### OFX
Padrão bancário com estrutura fixa. Cada transação tem `FITID`, único por
instituição — vai pra `transactions.external_transaction_id` prefixado
(`ofx:<FITID>`) e é **bloqueado** por índice único: reimportar o mesmo extrato
não duplica nada.

### CSV
Cada banco usa colunas e separador diferentes, então o parser detecta:
- separador `,` ou `;`
- coluna de data, valor e descrição por nome normalizado do cabeçalho
- número em formato brasileiro (`1.234,56`) ou americano (`1234.56`)

CSV **não** recebe `external_transaction_id`: sem id do banco, a única chave
seria data+valor+descrição, e dois cafés iguais no mesmo dia são legítimos.
Duplicata em CSV é **avisada no preview**, não bloqueada — o usuário decide.

## Sinal e tipo

Extrato usa negativo para débito. O schema guarda `amount` sempre positivo com
o sinal em `type`:

```
valor < 0  -> type = 'expense', amount = abs(valor)
valor > 0  -> type = 'income',  amount = valor
valor = 0  -> linha descartada
```

## Categoria é obrigatória na confirmação

O extrato traz a descrição do banco ("PIX ENVIADO JOAO"), não categoria. Como
despesa sem categoria escapa da regra 50-30-20 (ver `specs/09` e o histórico do
`CLAUDE.md`), a confirmação **exige** `category_id` em cada despesa.

### Como isso vira poucas decisões (revisado com extrato real)

A primeira versão desta spec dizia "sem adivinhação por palavra-chave: erraria
e exigiria manter regras". Um extrato real de um ano (Banco C6, 1.059
lançamentos) derrubou essa decisão: **951 eram despesas**, e pedir categoria em
cada uma tornava o import inutilizável justamente no caso que mais importa,
trazer histórico pra ter comparação mês a mês.

Duas medidas, nesta ordem de eficácia:

**1. Agrupar por comerciante** (`suggest.merchant_key`) — o que realmente
resolve. As 951 despesas vinham de ~170 comerciantes; os 10 maiores grupos
cobriam 521 lançamentos, e ~44 grupos cobriam 80%. Uma escolha vale pelo grupo
inteiro. A chave descarta número e ruído de descritor de cartão (país, cidade,
UF, sufixo de razão social) e usa as primeiras palavras, porque o final da
descrição varia entre compras do mesmo lugar.

**2. Sugerir por palavra-chave** (`suggest.RULES`) — ajuda, mas **cobre só 16%**
sozinha, medido nesse extrato. Vale pelo que é de graça, não como solução.

Regra de ouro: **melhor não sugerir do que sugerir errado.** Sugestão errada que
passa batida joga o gasto no bucket errado e distorce o 50-30-20 em silêncio;
campo vazio o usuário enxerga. Por isso termos ambíguos ficam fora
(ex: "PARK" pode ser estacionamento ou ParkShopping), e PIX/TED/boleto/fatura
não têm regra — são meio de pagamento, não categoria.

O preview é ordenado por volume: o usuário resolve o que mais pesa antes de
cansar. O grupo com muitos itens e uma decisão só é o ponto do desenho.

## O funil: valida um mês, aprende, replica

Agrupar por comerciante derruba 951 decisões para 169, mas 169 numa sentada só
ainda é inviável no celular. O que resolve é **guardar a decisão**: cada escolha
vira uma regra `merchant_key -> category_id` do household, aplicada neste import,
nos próximos, e nos outros meses do mesmo arquivo.

Medido no extrato real de 12 meses, com o mês mais recente primeiro:

| | decisões | resultado |
|---|---|---|
| mês 1 (dezembro) | **23** | cobre 57,6% do ano; o painel do mês já funciona |
| mês 2 (novembro) | 16 | 74% já vem pronto pelas regras do mês 1 |
| meses 3 a 12 | 5 a 22 cada | 70% a 92% já vem pronto |
| **total** | **169** | igual ao "tudo de uma vez" |

Dois resultados que fecham o desenho:

1. **Aprender não cobra nada a mais.** O total é 169 em qualquer ordem — mês a mês
   ou tudo de uma vez. Só a distribuição muda. Sem memória, o mês a mês custaria
   **360**, porque cada mês recomeçaria do zero; era esse desperdício, e não o
   import incremental, o problema.
2. **A ordem é recente -> antigo.** Dezembro custa 23 decisões e janeiro custaria
   30, e começar pelo mês corrente faz o dashboard viver imediatamente. A cobertura
   do ano é menor no primeiro passo (57,6% contra 68,9%), o que não importa: o resto
   vem nos meses seguintes de qualquer forma. Qualquer mês isolado cobre entre 58% e
   72% do ano, então o desenho não depende de acertar "o mês certo".

Consequência de schema: entra a tabela `import_rules` (household_id, merchant_key,
category_id) com unique em (household_id, merchant_key). A regra do usuário **ganha**
da sugestão por palavra-chave — `RULES` em `suggest.py` passa a ser só o palpite
inicial de quem nunca importou nada.

## Bandeja "decidir depois"

No extrato real, 129 comerciantes aparecem **uma única vez**, muitos deles PIX para
pessoas. Exigir categoria em todos travaria o usuário justamente no lançamento que
ele não lembra, e ele abandonaria o import inteiro.

Então existe uma bandeja "decidir depois": o lançamento **não é importado** e fica
para uma segunda passada. O botão de importar libera quando nada está *sem destino* —
adiado tem destino.

O preço disso é que **o mês entra incompleto**, e o painel subestima o gasto até a
segunda passada. Por isso o app avisa explicitamente quantos lançamentos ficaram de
fora. Gasto não desaparece em silêncio; é a mesma razão de `uncategorized_expense`
existir no dashboard (`specs/09`).

## Item tirado do grupo é uma decisão nova, não um descarte

`merchant_key` usa só as três primeiras palavras, então ele **sobre-agrupa**: num
extrato real, "BOLETO" junta energia, mensalidade escolar e plano de saúde. Atribuído
em lote, isso joga a escola no bucket errado em silêncio — exatamente o que a regra de
ouro acima proíbe. Por isso o grupo é expansível e cada item pode ser tirado dele.

Tirar um item **não** o descarta: ele vira uma unidade solta que exige a própria
decisão. A primeira versão do protótipo errava isso e deixava
`resolvidos + adiados < total` com o import liberado — um lançamento evaporava. A
invariante a testar é:

```
resolvidos + adiados == total de lançamentos do mês
```

## Interação escolhida: bandeja por categoria

Três interações foram prototipadas e comparadas em `prototipo/13-import-variantes.html`
sobre os mesmos 23 grupos: lista de grupos, uma decisão por tela, e bandeja por
categoria. A escolhida foi a **bandeja**.

O usuário escolhe uma categoria e marca **tudo que pertence a ela**, atribuindo em
lote. São até 9 rodadas (uma por categoria) em vez de 23 decisões, e a pergunta
"o que aqui é Mercado?" é mais fácil que "o que é isso?".

O ponto fraco assumido: no pior caso o usuário varre a lista 9 vezes. A bandeja
"decidir depois" é o que impede o travamento.

A barra de progresso conta **lançamentos**, não grupos — 79 e não 23 —, porque é o
lançamento que representa o trabalho e o dinheiro.

## Alertas só do mês corrente

A confirmação reavalia alertas **apenas do mês corrente**. Extrato de histórico
cobre meses encerrados, e avaliá-los criaria hoje alertas de teto e de "projeção
negativa" sobre orçamentos de anos atrás — no arquivo real de 12 meses isso
seriam dezenas de notificações inúteis, e enganosas, já que num mês fechado a
"projeção" é só o gasto que de fato aconteceu.

Meses passados continuam corretos no dashboard e nos insights: os tetos deles
são gerados sob demanda quando o mês é consultado.

## Detalhe de schema corrigido junto

O schema tinha `unique (account_id, external_transaction_id)`, desenhado para o
Pluggy, em que `account_id` existe. No import não há conta, então `account_id`
fica null — e no Postgres nulos são distintos, o que **anula** essa proteção.

A migration `0004` acrescenta índice único parcial por household:

```sql
create unique index transactions_household_external_id
  on transactions (household_id, external_transaction_id)
  where external_transaction_id is not null;
```

## Limites

- Arquivo até 5 MB e 2.000 linhas por import: acima disso o preview fica
  impraticável de revisar na mão, que é o ponto do fluxo.
- `entry_method = 'csv_import'` em tudo que vem daqui (valor já previsto no
  check do schema).

## Fora de escopo

- Import incremental por conta (depende de `accounts`, que só faz sentido com
  Open Finance).
- PDF de extrato.
- Tela de gerenciar as regras aprendidas (editar/apagar). Nasce junto com a
  primeira reclamação de regra errada — a regra é sobrescrita na próxima escolha
  do mesmo comerciante, então não é um beco sem saída.

Saiu de "fora de escopo": **categorização automática por palavra-chave**, que a
primeira versão desta spec descartava. Ela entrou (cobrindo 16%) e agora é só o
palpite inicial; o que carrega o peso é a regra aprendida.
