import polars as pl


def _pct_expr(base, comp):
    return (
        pl.when((pl.col(base) == 0) & (pl.col(comp) == 0)).then(0.0)
        .when(pl.col(base) == 0).then(-100.0)
        .when(pl.col(comp) == 0).then(100.0)
        .otherwise((pl.col(base) - pl.col(comp)) / pl.col(base) * 100)
    )
