from datetime import date
from decimal import Decimal

import pytest

from app.imports.parser import parse_amount, parse_csv, parse_date, parse_ofx

# --------------------------------------------------------------------------
# Valor
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("1.234,56", "1234.56"),
        ("1234.56", "1234.56"),
        ("1.234.567,89", "1234567.89"),
        ("45,90", "45.90"),
        ("0,08", "0.08"),
        ("12", "12"),
        ("R$ 1.200,00", "1200.00"),
    ],
)
def test_parse_amount_accepts_both_conventions(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["1.234", "1,234"])
def test_three_digits_after_separator_means_thousands(raw):
    """Moeda tem no máximo 2 casas, então '1.234' num extrato é mil duzentos e
    trinta e quatro — ler como 1,234 erraria o valor por mil vezes."""
    assert parse_amount(raw) == Decimal("1234")


@pytest.mark.parametrize(("raw", "expected"), [("-45,90", "-45.90"), ("(30,00)", "-30.00")])
def test_parse_amount_reads_negatives(raw, expected):
    assert parse_amount(raw) == Decimal(expected)


@pytest.mark.parametrize("raw", ["", "   ", "saldo", "R$"])
def test_parse_amount_rejects_garbage(raw):
    assert parse_amount(raw) is None


# --------------------------------------------------------------------------
# Data
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("05/08/2026", date(2026, 8, 5)),
        ("5/8/2026", date(2026, 8, 5)),
        ("05-08-2026", date(2026, 8, 5)),
        ("2026-08-05", date(2026, 8, 5)),
        ("5/8/26", date(2026, 8, 5)),
        # OFX cola hora e fuso na data.
        ("20260805120000[-3:BRT]", date(2026, 8, 5)),
    ],
)
def test_parse_date_accepts_bank_formats(raw, expected):
    assert parse_date(raw) == expected


@pytest.mark.parametrize("raw", ["", "31/02/2026", "2026-13-01", "ontem", "13"])
def test_parse_date_rejects_invalid(raw):
    assert parse_date(raw) is None


# --------------------------------------------------------------------------
# CSV
# --------------------------------------------------------------------------


def test_csv_comma_separated():
    # Quem separa coluna por vírgula usa ponto decimal — vírgula nos dois
    # papéis não convive, e esses bancos exportam com ponto e vírgula.
    content = b"Data,Descricao,Valor\n05/08/2026,Mercado,-150.00\n"

    rows = parse_csv(content)

    assert len(rows) == 1
    assert rows[0].occurred_at == date(2026, 8, 5)
    assert rows[0].amount == Decimal("150.00")
    assert rows[0].type == "expense"
    assert rows[0].description == "Mercado"


def test_csv_semicolon_with_brazilian_numbers():
    content = "Data;Lançamento;Valor\n05/08/2026;Aluguel;-1.800,00\n".encode()

    rows = parse_csv(content)

    assert rows[0].amount == Decimal("1800.00")
    assert rows[0].description == "Aluguel"


def test_csv_positive_amount_becomes_income():
    content = "Data;Histórico;Valor\n01/08/2026;Salário;8.000,00\n".encode()

    rows = parse_csv(content)

    assert rows[0].type == "income"
    assert rows[0].amount == Decimal("8000.00")


def test_csv_header_variants_are_recognized():
    """Cada banco nomeia as colunas diferente; o parser normaliza acento e caixa."""
    content = b"DATE,TITLE,AMOUNT\n2026-08-05,Uber,-35.00\n"

    rows = parse_csv(content)

    assert rows[0].description == "Uber"
    assert rows[0].amount == Decimal("35.00")


def test_csv_accepts_header_with_suffix():
    content = b"Data da compra;Estabelecimento;Valor (R$)\n05/08/2026;Padaria;-12,50\n"

    rows = parse_csv(content)

    assert rows[0].amount == Decimal("12.50")


def test_csv_skips_footer_and_balance_lines():
    content = (
        "Data;Descrição;Valor\n"
        "05/08/2026;Mercado;-150,00\n"
        ";Saldo final;1.000,00\n"
        "Total;;\n"
    ).encode()

    rows = parse_csv(content)

    assert len(rows) == 1


def test_csv_drops_zero_amount():
    content = "Data;Descrição;Valor\n05/08/2026;Estorno;0,00\n".encode()

    assert parse_csv(content) == []


def test_csv_without_amount_column_raises():
    content = b"Data,Descricao\n05/08/2026,Mercado\n"

    with pytest.raises(ValueError):
        parse_csv(content)


def test_csv_reads_latin1_accents():
    """Extrato de banco brasileiro costuma vir em latin-1, não utf-8."""
    content = "Data;Descrição;Valor\n05/08/2026;Refeição;-30,00\n".encode("latin-1")

    rows = parse_csv(content)

    assert rows[0].description == "Refeição"


def test_csv_has_no_external_id():
    """Sem id do banco, duplicata de CSV é avisada no preview, não bloqueada."""
    content = "Data;Descrição;Valor\n05/08/2026;Mercado;-10,00\n".encode()

    assert parse_csv(content)[0].external_id is None


# --------------------------------------------------------------------------
# OFX
# --------------------------------------------------------------------------

OFX_SAMPLE = """OFXHEADER:100
DATA:OFXSGML
<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><BANKTRANLIST>
<STMTTRN>
<TRNTYPE>DEBIT
<DTPOSTED>20260805120000[-3:BRT]
<TRNAMT>-150.00
<FITID>202608050001
<MEMO>MERCADO CENTRAL
</STMTTRN>
<STMTTRN>
<TRNTYPE>CREDIT
<DTPOSTED>20260801
<TRNAMT>8000.00
<FITID>202608010009
<NAME>SALARIO
</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


def test_ofx_reads_transactions():
    rows = parse_ofx(OFX_SAMPLE.encode())

    assert len(rows) == 2
    assert rows[0].occurred_at == date(2026, 8, 5)
    assert rows[0].amount == Decimal("150.00")
    assert rows[0].type == "expense"
    assert rows[0].description == "MERCADO CENTRAL"


def test_ofx_carries_fitid_for_dedupe():
    rows = parse_ofx(OFX_SAMPLE.encode())

    assert rows[0].external_id == "ofx:202608050001"
    assert rows[1].external_id == "ofx:202608010009"


def test_ofx_falls_back_to_name_when_there_is_no_memo():
    rows = parse_ofx(OFX_SAMPLE.encode())

    assert rows[1].description == "SALARIO"


def test_ofx_positive_is_income():
    rows = parse_ofx(OFX_SAMPLE.encode())

    assert rows[1].type == "income"


def test_ofx_without_transactions_returns_empty():
    assert parse_ofx(b"<OFX></OFX>") == []


def test_ofx_ignores_block_with_unreadable_amount():
    broken = "<STMTTRN><DTPOSTED>20260805<TRNAMT>abc<FITID>1</STMTTRN>"

    assert parse_ofx(broken.encode()) == []
