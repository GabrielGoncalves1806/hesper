"""Atalhos usados por vários arquivos de teste."""


def give(game, **amounts: int) -> None:
    """Põe recursos/itens no inventário do player: give(game, iron=10, silicon=4)."""
    for item, amount in amounts.items():
        assert game.inventory.add(item, amount) == 0, "não coube no inventário do teste"
