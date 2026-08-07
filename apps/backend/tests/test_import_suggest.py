import pytest

from app.imports.suggest import merchant_key, suggest_category_id, suggest_category_name

BY_NAME = {"MERCADO": 1, "TRANSPORTE": 2, "DELIVERY": 3, "STREAMING": 4}


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("IFOOD *PEDIDO 123", "Delivery"),
        ("UBER TRIP SAO PAULO", "Transporte"),
        ("POSTO IPIRANGA BR", "Transporte"),
        ("SUPERMERCADO SANTANA", "Mercado"),
        ("PANIFICACAO DONA BETINHA", "Mercado"),
        ("NETFLIX.COM", "Streaming"),
        ("CCR VIAOESTE PEDAGIO", "Transporte"),
        ("ALUGUEL APTO 42", "Moradia"),
    ],
)
def test_suggests_unambiguous_merchants(description, expected):
    assert suggest_category_name(description) == expected


@pytest.mark.parametrize(
    "description",
    [
        "PIX ENVIADO JOAO DA SILVA",
        "TRANSF ENVIADA MARIA",
        "PIX RECEBIDO",
        "BOLETO PAGO",
        "FATURA CARTAO",
        "",
        "XPTO LTDA",
    ],
)
def test_leaves_ambiguous_and_payment_methods_empty(description):
    """Sugestão errada que passa batido joga o gasto no bucket errado e distorce
    o 50-30-20 em silêncio; campo vazio o usuário vê e corrige."""
    assert suggest_category_name(description) is None


def test_streaming_wins_over_generic_match():
    """NETFLIX não pode cair numa regra de internet por conter 'NET'."""
    assert suggest_category_name("NETFLIX") == "Streaming"


def test_suggestion_ignores_accent_and_case():
    assert suggest_category_name("padaria são joão") == "Mercado"


def test_resolves_suggestion_against_household_categories():
    assert suggest_category_id("IFOOD", BY_NAME) == 3


def test_suggestion_is_dropped_when_the_category_does_not_exist():
    """Se o usuário apagou ou renomeou a categoria padrão, não vale inventar
    categoria a partir de um extrato."""
    assert suggest_category_id("ALUGUEL", BY_NAME) is None


# --------------------------------------------------------------------------
# Agrupamento por comerciante
# --------------------------------------------------------------------------


def test_same_merchant_groups_despite_card_descriptor_noise():
    """Cidade, país e número mudam entre compras do mesmo lugar — foi o que
    quebrava o agrupamento no extrato real."""
    a = merchant_key("PADARIA DONA BETINHA SAO PAULO BRA")
    b = merchant_key("PADARIA DONA BETINHA OSASCO BRA 4471")
    assert a == b


def test_different_merchants_do_not_group():
    assert merchant_key("POSTO IPIRANGA") != merchant_key("SUPERMERCADO SANTANA")


def test_key_ignores_numbers_and_symbols():
    assert merchant_key("IFOOD *PEDIDO 998877") == merchant_key("IFOOD PEDIDO")


def test_key_drops_company_suffix():
    assert merchant_key("NUTRICAR ALIMENTOS LTDA") == merchant_key("NUTRICAR ALIMENTOS")


def test_key_of_empty_description_is_empty():
    assert merchant_key("") == ""
    assert merchant_key("123 456") == ""


def test_key_is_capped_so_long_descriptors_still_group():
    """O fim da descrição costuma ser terminal/cidade e varia — só o começo
    identifica o comerciante."""
    a = merchant_key("MERCADO CENTRAL ALIMENTOS UNIDADE TRES CAIXA DOIS")
    b = merchant_key("MERCADO CENTRAL ALIMENTOS UNIDADE CINCO CAIXA UM")
    assert a == b
