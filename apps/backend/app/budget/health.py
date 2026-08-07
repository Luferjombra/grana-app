from decimal import Decimal

from app.common import BUCKETS, to_decimal

# Faixas do rótulo mostrado junto do número (protótipo: 78 -> "Atenção").
HEALTHY_FROM = 80
ATTENTION_FROM = 60


def _bucket_score(bucket: str, spent: Decimal, target: Decimal) -> Decimal:
    """0-100 por bucket.

    necessidades/desejos são **teto**: estar dentro vale 100, e cada 1% de
    estouro tira 1 ponto — gastar o dobro do teto zera o bucket.
    poupanca é **meta**: pontua proporcional ao quanto da meta foi atingido.
    """
    if target <= 0:
        return Decimal("0")

    ratio = spent / target

    if bucket == "poupanca":
        return min(Decimal("100"), ratio * Decimal("100"))

    if ratio <= 1:
        return Decimal("100")
    return max(Decimal("0"), (Decimal("2") - ratio) * Decimal("100"))


def compute_health_score(
    rule: dict, spent: dict[str, Decimal], targets: dict[str, Decimal]
) -> dict | None:
    """Média das notas por bucket, ponderada pelos percentuais 50-30-20 vigentes
    do household — se o usuário editar os percentuais, o peso acompanha.

    Retorna None quando não há teto pra nenhum bucket (mês sem renda
    cadastrada): sem meta, não existe aderência a medir.
    """
    if not targets:
        return None

    weighted_total = Decimal("0")
    weight_sum = Decimal("0")
    breakdown = []

    for bucket in BUCKETS:
        target = targets.get(bucket)
        if target is None:
            continue

        weight = to_decimal(rule[f"{bucket}_pct"])
        bucket_spent = spent.get(bucket, Decimal("0"))
        score = _bucket_score(bucket, bucket_spent, target)

        weighted_total += score * weight
        weight_sum += weight
        breakdown.append(
            {
                "bucket": bucket,
                "score": int(score.quantize(Decimal("1"))),
                "weight_pct": str(weight.quantize(Decimal("0.01"))),
                "spent": str(bucket_spent.quantize(Decimal("0.01"))),
                "target": str(target.quantize(Decimal("0.01"))),
            }
        )

    if weight_sum <= 0:
        return None

    score = int((weighted_total / weight_sum).quantize(Decimal("1")))
    return {"score": score, "label": score_label(score), "breakdown": breakdown}


def score_label(score: int) -> str:
    if score >= HEALTHY_FROM:
        return "saudavel"
    if score >= ATTENTION_FROM:
        return "atencao"
    return "risco"
