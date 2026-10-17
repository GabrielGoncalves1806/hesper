"""Atalhos usados por vários arquivos de teste."""


def give(game, **amounts: int) -> None:
    """Põe recursos/itens no inventário do player: give(game, iron=10, silicon=4)."""
    for item, amount in amounts.items():
        assert game.inventory.add(item, amount) == 0, "não coube no inventário do teste"


def build_now(game, kind: str, tile, rotation: int = 0, finish: bool = True):
    """v0.5 M1: constrói `kind` em `tile` pelo construtor (dá o construtor, a receita e o Ti da trava se faltar) e, com `finish`,
    pula a animação de construir (a máquina já sai funcionando). Devolve a máquina (None se não deu)."""
    from game import config as C
    if game.inventory.count("constructor") == 0:
        give(game, constructor=1)
    for r, n in C.MACHINES[kind].cost.items():
        short = n - game.inventory.count(r)
        if short > 0:
            give(game, **{r: short})
    indices, stage = dict(game.indices), game.stage   # v0.6: trava de Ti (ex.: Baú normal) não atrapalha o atalho;
    game.indices["o2"] += max(0.0, C.MACHINES[kind].unlock_ti - game.ti) + 1   # o Ti volta ao que era logo depois
    game.stage = max(stage, C.MACHINES[kind].unlock_stage)   # v0.8 M4: a trava por estágio (Centrífuga) também
    try:
        if not game.build(kind, tile, rotation):
            return None
    finally:
        game.indices.update(indices)
        game.stage = stage
    machine = game.machines[-1]
    if finish:
        machine.build = 0.0
    return machine


def from_192(x, y):
    """Coordenada (em tiles) escrita pro mapa antigo de 192×192, trazida pro mapa de hoje: a base é o referencial
    (era (96, 96)), então o ponto continua com o mesmo deslocamento dela. Troca o SURFACE_W sem mexer nos testes."""
    from game import config as C
    return (x - 96 + C.BASE_TILE[0], y - 96 + C.BASE_TILE[1])
