"""Atalhos usados por vários arquivos de teste."""


def give(game, **amounts: int) -> None:
    """Põe recursos/itens no inventário do player: give(game, iron=10, silicon=4)."""
    for item, amount in amounts.items():
        assert game.inventory.add(item, amount) == 0, "não coube no inventário do teste"


def build_now(game, kind: str, tile, rotation: int = 0, finish: bool = True):
    """v0.5 M1: constrói `kind` em `tile` pelo construtor (dá o construtor e a receita se faltar) e, com `finish`,
    pula a animação de construir (a máquina já sai funcionando). Devolve a máquina (None se não deu)."""
    from game import config as C
    if game.inventory.count("constructor") == 0:
        give(game, constructor=1)
    for r, n in C.MACHINES[kind].cost.items():
        short = n - game.inventory.count(r)
        if short > 0:
            give(game, **{r: short})
    if not game.build(kind, tile, rotation):
        return None
    machine = game.machines[-1]
    if finish:
        machine.build = 0.0
    return machine
