"""Cron: sincroniza indicadores do BACEN usados em insights (ex: IPCA/Selic),
reaproveitando o mesmo padrão de ETL da plataforma de investimentos (mcp-brasil).
"""

from etl.common.etl_run import track_run


def main() -> None:
    with track_run("bacen_indicadores"):
        raise NotImplementedError


if __name__ == "__main__":
    main()
