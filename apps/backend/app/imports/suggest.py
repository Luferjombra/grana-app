"""Sugestão de categoria pela descrição do extrato (specs/11).

A spec original descartava isso ("erraria e exigiria manter regras"), mas um
extrato real de um ano trouxe 951 despesas: sem sugestão, o usuário teria que
categorizar uma a uma e abandonaria o import — que é a única ponte com o banco.

Princípio: **é melhor não sugerir nada do que sugerir errado.** Sugestão errada
que passa despercebida joga o gasto no bucket errado e distorce o 50-30-20
silenciosamente; campo vazio o usuário enxerga e preenche. Por isso as regras
cobrem só padrões inequívocos, e termos ambíguos ficam de fora de propósito
(ex: "PARK" pode ser estacionamento ou ParkShopping; "PAN" pode ser padaria ou
Banco Pan).

PIX, TED, boleto e fatura são **meio de pagamento**, não categoria — não têm
regra, e transferência entre pessoas fica sem sugestão mesmo.
"""

import re

# (trecho procurado, nome da categoria). Ordem importa: o primeiro que casar
# ganha, então o mais específico vem antes.
RULES: tuple[tuple[str, str], ...] = (
    # Streaming antes de Contas, senão "NETFLIX" cairia numa regra de internet.
    ("NETFLIX", "Streaming"),
    ("SPOTIFY", "Streaming"),
    ("DISNEY", "Streaming"),
    ("HBO", "Streaming"),
    ("PRIME VIDEO", "Streaming"),
    ("DEEZER", "Streaming"),
    ("GLOBOPLAY", "Streaming"),
    ("PARAMOUNT", "Streaming"),
    ("YOUTUBE PREMIUM", "Streaming"),
    # Delivery e alimentação fora de casa (bucket desejos no seed).
    ("IFOOD", "Delivery"),
    ("RAPPI", "Delivery"),
    ("UBER EATS", "Delivery"),
    ("ZE DELIVERY", "Delivery"),
    ("AIQFOME", "Delivery"),
    ("RESTAURANTE", "Delivery"),
    ("LANCHONETE", "Delivery"),
    ("PIZZARIA", "Delivery"),
    ("HAMBURG", "Delivery"),
    ("CAFETERIA", "Delivery"),
    ("SUSHI", "Delivery"),
    ("ACAI", "Delivery"),
    # Mercado e padaria (necessidades).
    ("SUPERMERCADO", "Mercado"),
    ("MERCADO", "Mercado"),
    ("ATACAD", "Mercado"),
    ("ASSAI", "Mercado"),
    ("CARREFOUR", "Mercado"),
    ("PAO DE ACUCAR", "Mercado"),
    ("HORTIFRUTI", "Mercado"),
    ("SACOLAO", "Mercado"),
    ("PADARIA", "Mercado"),
    ("PANIFICAC", "Mercado"),
    ("ACOUGUE", "Mercado"),
    # Transporte.
    ("UBER", "Transporte"),
    ("99POP", "Transporte"),
    ("CABIFY", "Transporte"),
    ("POSTO", "Transporte"),
    ("IPIRANGA", "Transporte"),
    ("COMBUSTIVEL", "Transporte"),
    ("ESTACIONAMENTO", "Transporte"),
    ("PEDAGIO", "Transporte"),
    ("SEM PARAR", "Transporte"),
    ("CONECTCAR", "Transporte"),
    ("VIAOESTE", "Transporte"),
    ("AUTOBAN", "Transporte"),
    ("BILHETE UNICO", "Transporte"),
    # Contas de consumo.
    ("ENEL", "Contas"),
    ("SABESP", "Contas"),
    ("COMGAS", "Contas"),
    ("CEMIG", "Contas"),
    ("COPEL", "Contas"),
    ("LIGHT SERVICOS", "Contas"),
    ("VIVO", "Contas"),
    ("CLARO", "Contas"),
    ("TELEFONICA", "Contas"),
    # Moradia.
    ("ALUGUEL", "Moradia"),
    ("CONDOMINIO", "Moradia"),
    ("IMOBILIARIA", "Moradia"),
    ("IPTU", "Moradia"),
    # Compras.
    ("MERCADO LIVRE", "Compras"),
    ("MERCADOLIVRE", "Compras"),
    ("MAGAZINE LUIZA", "Compras"),
    ("MAGALU", "Compras"),
    ("AMERICANAS", "Compras"),
    ("SHOPEE", "Compras"),
    ("ALIEXPRESS", "Compras"),
    ("AMAZON", "Compras"),
    ("RENNER", "Compras"),
    ("RIACHUELO", "Compras"),
    ("CENTAURO", "Compras"),
    # Lazer.
    ("CINEMAR", "Lazer"),
    ("CINEMARK", "Lazer"),
    ("INGRESSO.COM", "Lazer"),
    ("SMARTFIT", "Lazer"),
    ("SMART FIT", "Lazer"),
    ("ACADEMIA", "Lazer"),
    # Investimentos.
    ("TESOURO", "Investimentos"),
    ("APLICACAO", "Investimentos"),
    ("NUINVEST", "Investimentos"),
    ("XP INVEST", "Investimentos"),
)

ACCENTS = str.maketrans("ÁÀÂÃÄÉÈÊËÍÌÎÏÓÒÔÕÖÚÙÛÜÇ", "AAAAAEEEEIIIIOOOOOUUUUC")

# Ruído que descritor de cartão cola na descrição: país, cidade e UF. Medido
# num extrato real do C6, em que "BRA" e o nome da cidade apareciam em quase
# toda compra e quebravam o agrupamento por comerciante.
NOISE_TOKENS = frozenset(
    {
        "BRA",
        "BR",
        "SAO",
        "PAULO",
        "RIO",
        "JANEIRO",
        "BELO",
        "HORIZONTE",
        "OSASCO",
        "BARUERI",
        "GUARULHOS",
        "CAMPINAS",
        "CURITIBA",
        "SP",
        "RJ",
        "MG",
        "LTDA",
        "ME",
        "EIRELI",
        "SA",
    }
)

MERCHANT_TOKENS = 3


def normalize(description: str) -> str:
    return description.upper().translate(ACCENTS)


def merchant_key(description: str) -> str:
    """Chave estável pra agrupar lançamentos do mesmo comerciante.

    Palavra-chave resolve pouco (16% num extrato real de um ano), mas as 797
    despesas que sobraram vinham de só 172 comerciantes, e os 30 maiores
    cobriam 73% delas. Agrupar transforma centenas de decisões em algumas
    dezenas — é o que torna o import de histórico viável (specs/11).

    Descarta número e ruído de descritor, e usa as primeiras palavras: o final
    costuma ser cidade/terminal, que varia entre compras do mesmo lugar.
    """
    text = re.sub(r"[0-9]+", " ", normalize(description))
    text = re.sub(r"[^A-Z\s]", " ", text)

    tokens = [token for token in text.split() if len(token) > 1 and token not in NOISE_TOKENS]
    return " ".join(tokens[:MERCHANT_TOKENS])


def suggest_category_name(description: str) -> str | None:
    """Nome da categoria sugerida, ou None quando nenhuma regra é inequívoca."""
    if not description:
        return None

    text = normalize(description)
    for needle, category in RULES:
        if needle in text:
            return category
    return None


def suggest_category_id(description: str, by_name: dict[str, int]) -> int | None:
    """Resolve a sugestão contra as categorias do household.

    Se o usuário renomeou ou apagou a categoria padrão, a sugestão simplesmente
    não se aplica — não vale inventar categoria nova a partir de um extrato.
    """
    name = suggest_category_name(description)
    if name is None:
        return None
    return by_name.get(normalize(name))
