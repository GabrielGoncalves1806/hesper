"""Props de 1 tile (v0.7 M2 · bíblia §16): decoração do player e cenário das ruínas.

Objeto próprio, igual ao `Crate` e ao `BaseBlock`: NÃO é `Machine` (não entra em energia, índice, drone, luz nem na
lista de máquinas). Mora em `Layer.props`, chaveado pelo tile. O de face mora no tile da PAREDE; o de chão e a mesa
de parede, no tile de chão. Python puro, testado em tests/test_props.py.
"""

from __future__ import annotations

from dataclasses import dataclass

from game import config as C


@dataclass(eq=False)
class Prop:
    kind: str                  # chave em C.PROPS
    tx: int
    ty: int
    ruin: bool = False         # de ruína: sai da seed (como a casca), não desmonta e nunca vai no save

    @property
    def tile(self) -> tuple[int, int]:
        return self.tx, self.ty

    @property
    def type(self) -> C.PropType:
        return C.PROPS[self.kind]

    @property
    def place(self) -> str:
        return self.type.place

    @property
    def solid(self) -> bool:
        return self.type.solid

    @property
    def rect(self) -> tuple[int, int, int, int] | None:
        """Caixa de colisão em px do mundo (None se não colide). A mesa de parede colide no tile inteiro."""
        if not self.type.solid:
            return None
        if self.place == "desk":
            return self.tx * C.TILE, self.ty * C.TILE, C.TILE, C.TILE
        x, y, w, h = C.PROP_COLLIDE
        return self.tx * C.TILE + x, self.ty * C.TILE + y, w, h


def face_visible(is_wallish, tx: int, ty: int) -> bool:
    """A parede em (tx, ty) mostra face: o tile de baixo não é parede. `is_wallish(tx, ty) -> bool`."""
    return not is_wallish(tx, ty + 1)
