"""Leitura de extrato CSV/OFX (specs/11).

Puro de propósito: nada aqui toca banco ou rede, então o comportamento com os
formatos de cada instituição é todo testável.
"""

import csv
import io
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

MAX_ROWS = 2000

# Cabeçalhos que os bancos brasileiros usam pra cada coluna, já normalizados
# (sem acento, minúsculos). A ordem importa: o primeiro que casar ganha.
DATE_HEADERS = ("data", "date", "data lancamento", "data da compra", "dt")
AMOUNT_HEADERS = ("valor", "amount", "quantia", "value", "valor (r$)")
DESCRIPTION_HEADERS = (
    "descricao",
    "description",
    "lancamento",
    "historico",
    "title",
    "estabelecimento",
    "detalhes",
)


@dataclass
class ParsedRow:
    occurred_at: date
    amount: Decimal
    type: str
    description: str
    # Só o OFX traz id do banco (FITID). CSV fica sem, e a duplicata dele é
    # avisada no preview em vez de bloqueada (specs/11).
    external_id: str | None = None


def normalize_header(value: str) -> str:
    text = value.strip().lower()
    for accented, plain in (
        ("ã", "a"),
        ("á", "a"),
        ("â", "a"),
        ("é", "e"),
        ("ê", "e"),
        ("í", "i"),
        ("ó", "o"),
        ("ô", "o"),
        ("ú", "u"),
        ("ç", "c"),
    ):
        text = text.replace(accented, plain)
    return re.sub(r"\s+", " ", text)


def parse_amount(raw: str) -> Decimal | None:
    """Aceita 1.234,56 (brasileiro) e 1234.56 (americano), com R$ e sinal.

    O caso ambíguo é '1.234': em extrato brasileiro é mil duzentos e trinta e
    quatro, não um e duzentos e trinta e quatro milésimos. A regra é contar os
    dígitos depois do último separador — moeda tem no máximo 2 casas, então 3
    dígitos denunciam separador de milhar.
    """
    text = raw.strip().replace("R$", "").replace(" ", "").replace("\xa0", "")
    if not text:
        return None

    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    text = text.lstrip("+-").strip("()")

    last_separator = max(text.rfind(","), text.rfind("."))
    decimals = len(text) - last_separator - 1

    if last_separator >= 0 and decimals <= 2:
        # Último separador é o decimal; o outro tipo é de milhar.
        whole = re.sub(r"[.,]", "", text[:last_separator])
        text = f"{whole}.{text[last_separator + 1 :]}"
    else:
        # Sem separador decimal (ou grupo de 3): tudo é milhar.
        text = re.sub(r"[.,]", "", text)

    try:
        value = Decimal(text)
    except InvalidOperation:
        return None

    return -value if negative else value


def parse_date(raw: str) -> date | None:
    text = raw.strip()
    if not text:
        return None

    # dd/mm/aaaa e dd-mm-aaaa (o comum nos bancos daqui), além de ISO.
    br = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})", text)
    if br:
        day, month, year = (int(part) for part in br.groups())
        if year < 100:
            year += 2000
        return _safe_date(year, month, day)

    iso = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text)
    if iso:
        year, month, day = (int(part) for part in iso.groups())
        return _safe_date(year, month, day)

    # OFX usa aaaammdd, às vezes com hora e fuso colados.
    ofx = re.match(r"^(\d{4})(\d{2})(\d{2})", text)
    if ofx:
        year, month, day = (int(part) for part in ofx.groups())
        return _safe_date(year, month, day)

    return None


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def row_from(occurred_at: date, amount: Decimal, description: str, external_id=None):
    """Extrato usa negativo pra débito; o schema guarda valor positivo com o
    sinal no `type` (specs/11)."""
    if amount == 0:
        return None
    return ParsedRow(
        occurred_at=occurred_at,
        amount=abs(amount),
        type="expense" if amount < 0 else "income",
        description=description.strip(),
        external_id=external_id,
    )


def parse_csv(content: bytes) -> list[ParsedRow]:
    text = _decode(content)
    delimiter = ";" if text.count(";") > text.count(",") else ","

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    if not reader.fieldnames:
        return []

    headers = {normalize_header(name): name for name in reader.fieldnames if name}
    date_key = _match_header(headers, DATE_HEADERS)
    amount_key = _match_header(headers, AMOUNT_HEADERS)
    description_key = _match_header(headers, DESCRIPTION_HEADERS)

    if not date_key or not amount_key:
        raise ValueError("Não encontrei as colunas de data e valor no arquivo.")

    rows: list[ParsedRow] = []
    for raw in reader:
        if len(rows) >= MAX_ROWS:
            break

        occurred_at = parse_date(raw.get(date_key) or "")
        amount = parse_amount(raw.get(amount_key) or "")
        if occurred_at is None or amount is None:
            continue  # linha de saldo, rodapé, cabeçalho repetido

        description = (raw.get(description_key) or "").strip() if description_key else ""
        row = row_from(occurred_at, amount, description)
        if row:
            rows.append(row)

    return rows


def parse_ofx(content: bytes) -> list[ParsedRow]:
    """OFX é SGML, não XML válido — tags podem não fechar. Por isso é lido por
    regex sobre cada bloco STMTTRN em vez de por parser de XML."""
    text = _decode(content)
    rows: list[ParsedRow] = []

    for block in re.findall(r"<STMTTRN>(.*?)</STMTTRN>", text, re.DOTALL | re.IGNORECASE):
        if len(rows) >= MAX_ROWS:
            break

        occurred_at = parse_date(_tag(block, "DTPOSTED") or "")
        amount = parse_amount(_tag(block, "TRNAMT") or "")
        if occurred_at is None or amount is None:
            continue

        description = _tag(block, "MEMO") or _tag(block, "NAME") or ""
        fitid = _tag(block, "FITID")
        row = row_from(
            occurred_at,
            amount,
            description,
            external_id=f"ofx:{fitid}" if fitid else None,
        )
        if row:
            rows.append(row)

    return rows


def _tag(block: str, name: str) -> str | None:
    match = re.search(rf"<{name}>([^<\r\n]*)", block, re.IGNORECASE)
    return match.group(1).strip() if match else None


def _match_header(headers: dict[str, str], candidates: tuple[str, ...]) -> str | None:
    for candidate in candidates:
        if candidate in headers:
            return headers[candidate]
    # Nenhum nome exato: aceita quem contenha o termo (ex: "Valor (R$)").
    for candidate in candidates:
        for normalized, original in headers.items():
            if candidate in normalized:
                return original
    return None


def _decode(content: bytes) -> str:
    # Extrato de banco brasileiro costuma vir em latin-1; utf-8-sig cobre o BOM
    # que o Excel adiciona.
    for encoding in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    return content.decode("latin-1", errors="replace")
