"""Equipamento do traje (v0.3 Marco 3 · bíblia §9): slots tipados na tela do inventário (Tab).

Um slot por tipo (`config.EQUIP_SLOTS`): o tanque de O₂ vai no slot "o2_tank", o scanner no "scanner".
Equipamento não fica na hotbar nem vai pro chão: é um item (sai do fabricador) que o jogador encaixa
no traje com um clique. O que ele faz:
    - tanque de O₂: O₂ máximo de 100 s -> 220 s (`o2_max`);
    - scanner de navegação: minimapa no HUD e mapa grande no M (game/explore.py).

Python puro, testado em tests/test_equipment.py. Quem mexe no inventário é o GameState
(`equip_from`, `unequip`); aqui só os slots.
"""

from game import config as C


def is_equipment(item: str | None) -> bool:
    return item in C.EQUIP_SLOTS


class Equipment:
    def __init__(self):
        self.slots: dict[str, str | None] = {k: None for k in C.EQUIP_SLOTS}

    def has(self, kind: str) -> bool:
        return self.slots.get(kind) is not None

    def equip(self, item: str) -> str | None:
        """Encaixa `item` no slot dele. Devolve o que estava lá (troca) ou None."""
        if not is_equipment(item):
            raise ValueError(f"{item!r} não é equipamento")
        old, self.slots[item] = self.slots[item], item
        return old

    def unequip(self, kind: str) -> str | None:
        """Tira o equipamento do slot `kind` (devolve o item, ou None se estava vazio)."""
        item, self.slots[kind] = self.slots.get(kind), None
        return item

    @property
    def o2_max(self) -> float:
        return C.O2_TANK_MAX if self.has("o2_tank") else C.O2_MAX

    # ---- save: {"o2_tank": "o2_tank", "scanner": None} ----------------------------
    def to_data(self) -> dict:
        return dict(self.slots)

    @classmethod
    def from_data(cls, data: dict | None) -> "Equipment":
        eq = cls()
        for kind, item in (data or {}).items():
            if kind in eq.slots and item == kind:        # item desconhecido ou no slot errado: fica vazio
                eq.slots[kind] = item
        return eq
