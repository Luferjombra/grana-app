from decimal import Decimal

from app.budget.health import compute_health_score, score_label

RULE = {"necessidades_pct": 50, "desejos_pct": 30, "poupanca_pct": 20}


def d(value: str) -> Decimal:
    return Decimal(value)


def test_returns_none_without_targets():
    assert compute_health_score(RULE, {}, {}) is None


def test_perfect_month_scores_100():
    targets = {"necessidades": d("4000"), "desejos": d("2400"), "poupanca": d("1600")}
    spent = {"necessidades": d("3800"), "desejos": d("2000"), "poupanca": d("1600")}

    result = compute_health_score(RULE, spent, targets)

    assert result["score"] == 100
    assert result["label"] == "saudavel"


def test_savings_shortfall_lowers_score_proportionally():
    targets = {"necessidades": d("4000"), "desejos": d("2400"), "poupanca": d("1600")}
    # Dentro dos tetos, mas guardou só 75% da meta de poupança.
    spent = {"necessidades": d("3800"), "desejos": d("2330"), "poupanca": d("1200")}

    result = compute_health_score(RULE, spent, targets)

    # 100*0.5 + 100*0.3 + 75*0.2 = 95
    assert result["score"] == 95


def test_overspending_a_ceiling_penalizes_one_point_per_percent():
    targets = {"necessidades": d("1000"), "desejos": d("1000"), "poupanca": d("1000")}
    # Necessidades 20% acima do teto -> 100 - 20 = 80 pontos nesse bucket.
    spent = {"necessidades": d("1200"), "desejos": d("1000"), "poupanca": d("1000")}

    result = compute_health_score(RULE, spent, targets)
    necessidades = next(b for b in result["breakdown"] if b["bucket"] == "necessidades")

    assert necessidades["score"] == 80


def test_double_the_ceiling_zeroes_that_bucket():
    targets = {"necessidades": d("1000"), "desejos": d("1000"), "poupanca": d("1000")}
    spent = {"necessidades": d("2000"), "desejos": d("1000"), "poupanca": d("1000")}

    result = compute_health_score(RULE, spent, targets)
    necessidades = next(b for b in result["breakdown"] if b["bucket"] == "necessidades")

    assert necessidades["score"] == 0


def test_far_over_the_ceiling_never_goes_negative():
    targets = {"necessidades": d("1000"), "desejos": d("1000"), "poupanca": d("1000")}
    spent = {"necessidades": d("10000"), "desejos": d("1000"), "poupanca": d("1000")}

    result = compute_health_score(RULE, spent, targets)
    necessidades = next(b for b in result["breakdown"] if b["bucket"] == "necessidades")

    assert necessidades["score"] == 0
    assert result["score"] >= 0


def test_saving_beyond_the_goal_caps_at_100():
    targets = {"necessidades": d("1000"), "desejos": d("1000"), "poupanca": d("1000")}
    spent = {"necessidades": d("1000"), "desejos": d("1000"), "poupanca": d("5000")}

    result = compute_health_score(RULE, spent, targets)
    poupanca = next(b for b in result["breakdown"] if b["bucket"] == "poupanca")

    assert poupanca["score"] == 100


def test_weights_follow_edited_budget_rule():
    """Se o household muda os percentuais, o peso de cada bucket acompanha."""
    rule = {"necessidades_pct": 10, "desejos_pct": 10, "poupanca_pct": 80}
    targets = {"necessidades": d("1000"), "desejos": d("1000"), "poupanca": d("1000")}
    spent = {"necessidades": d("1000"), "desejos": d("1000"), "poupanca": d("0")}

    result = compute_health_score(rule, spent, targets)

    # Poupança zerada pesa 80% agora: 100*0.1 + 100*0.1 + 0*0.8 = 20
    assert result["score"] == 20


def test_zero_target_does_not_divide_by_zero():
    targets = {"necessidades": d("0"), "desejos": d("1000"), "poupanca": d("1000")}
    spent = {"necessidades": d("500"), "desejos": d("1000"), "poupanca": d("1000")}

    result = compute_health_score(RULE, spent, targets)

    assert result is not None
    assert 0 <= result["score"] <= 100


def test_score_labels():
    assert score_label(100) == "saudavel"
    assert score_label(80) == "saudavel"
    assert score_label(79) == "atencao"
    assert score_label(60) == "atencao"
    assert score_label(59) == "risco"
    assert score_label(0) == "risco"
