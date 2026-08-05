"""Cron diário (meia-noite local): recomputa a projeção linear de fechamento
do mês pra todo household com pelo menos uma transação no mês.

Ver specs/07-job-projecao-notificacoes.md — mesma lógica do gatilho de
evento, chamando `notifications/engine.py` do backend.
"""

from etl.common.etl_run import track_run


def main() -> None:
    with track_run("projection_recompute"):
        raise NotImplementedError


if __name__ == "__main__":
    main()
