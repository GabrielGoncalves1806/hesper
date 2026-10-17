"""Equipamento do traje (v0.3 Marco 3 · bíblia §9): slots tipados na tela do inventário (Tab).

Um slot por tipo (`config.EQUIP_SLOTS`): o tanque de O₂ vai no slot "o2_tank", o scanner no "scanner".
v0.8 M5: o slot aceita o nv.1 ou o nv.2 (`config.EQUIP_SLOT_OF`: tanque nv.2 e Mochila T2), e as botas ganham slot.
Equipamento não fica na hotbar nem vai pro chão: é um item (sai do fabricador) que o jogador encaixa
no traje com um clique. O que ele faz:
    - tanque de O₂: O₂ máximo de 100 s -> 220 s (`o2_max`); o nv.2 dá 400 s;
    - mochila: +1 linha de 8 no inventário (a T2, +2: `backpack_rows`);
    - botas: player ×BOOTS_SPEED (GameState.player_speed);
    - scanner de navegação: minimapa no HUD e mapa grande no M (game/explore.py).

Python puro, testado em tests/test_equipment.py. Quem mexe no inventário é o GameState
(`equip_from`, `unequip`); aqui só os slots.
"""

from game import config as C


def is_equipment(item: str | None) -> bool:
    return item in C.EQUIP_SLOT_OF


def slot_of(item: str) -> str:
    """O slot do traje onde `item` entra (o nv.2 vai no slot do nv.1)."""
    return C.EQUIP_SLOT_OF[item]


class Equipment:
    def __init__(self):
        self.slots: dict[str, str | None] = {k: None for k in C.EQUIP_SLOTS}

    def filled(self, slot: str) -> bool:
        """O slot tem algum equipamento (nv.1 ou nv.2)."""
        return self.slots.get(slot) is not None

    def has(self, item: str) -> bool:
        """Aquele item exato está no traje (o tanque nv.1 não conta como o nv.2, nem o contrário)."""
        return is_equipment(item) and self.slots.get(slot_of(item)) == item

    def equip(self, item: str) -> str | None:
        """Encaixa `item` no slot dele. Devolve o que estava lá (troca) ou None."""
        if not is_equipment(item):
            raise ValueError(f"{item!r} não é equipamento")
        slot = slot_of(item)
        old, self.slots[slot] = self.slots[slot], item
        return old

    def unequip(self, slot: str) -> str | None:
        """Tira o equipamento do slot (devolve o item, ou None se estava vazio)."""
        item, self.slots[slot] = self.slots.get(slot), None
        return item

    @property
    def o2_max(self) -> float:
        tank = self.slots.get("o2_tank")
        if tank == C.O2_TANK_T2:
            return C.O2_TANK_T2_MAX
        return C.O2_TANK_MAX if tank else C.O2_MAX

    @property
    def backpack_rows(self) -> int:
        """Linhas de 8 que a mochila põe no inventário: 0 sem, 1 com a nv.1, 2 com a T2."""
        bag = self.slots.get("backpack")
        if bag == C.BACKPACK_T2:
            return C.BACKPACK_T2_SLOTS // 8
        return C.BACKPACK_SLOTS // 8 if bag else 0

    # ---- save: {"o2_tank": "o2_tank_t2", "scanner": None, "backpack": "backpack", "boots": None} ----
    def to_data(self) -> dict:
        return dict(self.slots)

    @classmethod
    def from_data(cls, data: dict | None) -> "Equipment":
        eq = cls()
        for slot, item in (data or {}).items():
            if slot in eq.slots and is_equipment(item) and slot_of(item) == slot:   # desconhecido ou no slot errado: vazio
                eq.slots[slot] = item
        return eq
