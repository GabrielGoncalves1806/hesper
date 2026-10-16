"""Inventário com slots: a mochila do player e o conteúdo dos baús.

Tudo aqui é Python puro (nada de pygame), testado em tests/test_inventory.py.

Ideia central: um inventário é uma lista de N slots. Cada slot está vazio (None) ou tem
uma pilha (`Stack`): um item e quantos tem. Item é só uma string:
    - recurso: "iron", "silicon", "ice"     (empilha até 50)
    - máquina: "o2", "drill", "chest"...    (a chave de config.MACHINES; empilha até 5)

Duas famílias de operação:
    - por TIPO (o jogo usa): add, remove, count, has_space. Não importa em qual slot está.
    - por SLOT (a tela de inventário usa): take, take_half, put, move, swap, split, quick_move.
      A tela tem uma "mão" (a pilha presa no cursor): take tira do slot pra mão e put devolve.
    - entre DOIS inventários (baú aberto): transfer (pilha ou N unidades) e transfer_all
      (Pegar tudo / Guardar tudo).
"""

from dataclasses import dataclass

from game import config as C


def max_stack(item: str) -> int:
    """Até quanto esse item empilha num slot."""
    if item in C.HAND_DRILLS:
        return C.STACK_TOOL                           # v0.5 M4: a broca de mão não empilha (v0.6 Fundo M4: nem a nv.2)
    if item in C.PART_ITEMS:
        return C.STACK_LOOT                           # v0.5 M4: peças de loot e lingotes (só ocupam inventário)
    return C.STACK_RESOURCE if item in C.RESOURCES else C.STACK_MACHINE


@dataclass
class Stack:
    item: str
    count: int

    @property
    def max(self) -> int:
        return max_stack(self.item)

    @property
    def room(self) -> int:
        """Quanto ainda cabe nessa pilha."""
        return self.max - self.count


class Inventory:
    def __init__(self, size: int):
        self.slots: list[Stack | None] = [None] * size

    def __len__(self) -> int:
        return len(self.slots)

    # ---- consultas por tipo --------------------------------------------------
    def count(self, item: str) -> int:
        return sum(s.count for s in self.slots if s and s.item == item)

    def counts(self) -> dict[str, int]:
        """{item: total} de tudo que tem dentro (só os itens presentes)."""
        totals: dict[str, int] = {}
        for s in self.slots:
            if s:
                totals[s.item] = totals.get(s.item, 0) + s.count
        return totals

    def space_for(self, item: str) -> int:
        """Quantas unidades desse item ainda cabem (sobra nas pilhas iguais + slots vazios)."""
        same = sum(s.room for s in self.slots if s and s.item == item)
        empty = sum(1 for s in self.slots if s is None)
        return same + empty * max_stack(item)

    def has_space(self, item: str, amount: int = 1) -> bool:
        return self.space_for(item) >= amount

    def is_empty(self) -> bool:
        return all(s is None for s in self.slots)

    # ---- mudanças por tipo ---------------------------------------------------
    def add(self, item: str, amount: int) -> int:
        """Guarda `amount` unidades. Primeiro completa as pilhas iguais, depois usa slots vazios.
        Devolve quanto NÃO coube (0 = coube tudo)."""
        left = amount
        for s in self.slots:                          # 1) completa pilhas do mesmo item
            if left <= 0:
                break
            if s and s.item == item and s.room > 0:
                moved = min(s.room, left)
                s.count += moved
                left -= moved
        for i, s in enumerate(self.slots):            # 2) abre pilhas novas nos slots vazios
            if left <= 0:
                break
            if s is None:
                moved = min(max_stack(item), left)
                self.slots[i] = Stack(item, moved)
                left -= moved
        return left

    def remove(self, item: str, amount: int) -> int:
        """Tira até `amount` unidades desse item (das últimas pilhas pras primeiras, pra não
        esvaziar a hotbar antes da mochila). Devolve quanto tirou de verdade."""
        taken = 0
        for i in range(len(self.slots) - 1, -1, -1):
            s = self.slots[i]
            if taken >= amount:
                break
            if s and s.item == item:
                moved = min(s.count, amount - taken)
                self.remove_from_slot(i, moved)
                taken += moved
        return taken

    def remove_from_slot(self, index: int, amount: int = 1) -> int:
        """Tira até `amount` de um slot específico (ex.: colocar a máquina do slot da hotbar)."""
        s = self.slots[index]
        if s is None:
            return 0
        moved = min(s.count, amount)
        s.count -= moved
        if s.count == 0:
            self.slots[index] = None
        return moved

    def resize(self, size: int) -> None:
        """Muda o número de slots (mochila equipada: 16 -> 24). Crescer acrescenta slots vazios no fim; encolher
        só corta slots vazios (quem chama confere antes com `tail_empty`)."""
        if size < len(self.slots):
            assert self.tail_empty(size), "encolher cortaria slots com item"
            del self.slots[size:]
        else:
            self.slots.extend([None] * (size - len(self.slots)))

    def tail_empty(self, start: int) -> bool:
        """Os slots de `start` pra frente estão todos vazios?"""
        return all(s is None for s in self.slots[start:])

    def clear(self) -> None:
        self.slots = [None] * len(self.slots)

    def copy(self) -> "Inventory":
        """Cópia independente (pra testar "e se eu tirar isso, sobra espaço?" sem mexer no original)."""
        other = Inventory(len(self.slots))
        other.slots = [Stack(s.item, s.count) if s else None for s in self.slots]
        return other

    # ---- operações por slot (tela de inventário) ------------------------------
    def take(self, index: int) -> Stack | None:
        """Tira a pilha inteira do slot (vai pra "mão")."""
        stack, self.slots[index] = self.slots[index], None
        return stack

    def take_half(self, index: int) -> Stack | None:
        """Tira metade da pilha (arredonda pra cima: de 5 tira 3; de 1 tira 1)."""
        s = self.slots[index]
        if s is None:
            return None
        half = (s.count + 1) // 2
        self.remove_from_slot(index, half)
        return Stack(s.item, half)

    def put(self, index: int, stack: Stack | None) -> Stack | None:
        """Solta a pilha da mão no slot. Devolve o que fica na mão depois:
        - slot vazio: a pilha entra toda (mão vazia);
        - mesmo item: junta até encher (o que sobra fica na mão);
        - item diferente: troca (a mão pega o que estava no slot)."""
        if stack is None:
            return self.take(index)
        current = self.slots[index]
        if current is None:
            self.slots[index] = stack
            return None
        if current.item == stack.item:
            moved = min(current.room, stack.count)
            current.count += moved
            stack.count -= moved
            return stack if stack.count > 0 else None
        self.slots[index] = stack
        return current

    def move(self, src: int, dst: int, target: "Inventory | None" = None) -> None:
        """Move a pilha do slot `src` pro slot `dst` (de `target`, ou deste mesmo inventário).
        Junta se for o mesmo item (o que não couber volta pro `src`), troca se for diferente."""
        target = target or self
        if target is self and src == dst:
            return
        leftover = target.put(dst, self.take(src))
        if leftover is not None:
            self.slots[src] = leftover

    def swap(self, i: int, j: int) -> None:
        self.slots[i], self.slots[j] = self.slots[j], self.slots[i]

    def split(self, index: int) -> bool:
        """Divide a pilha em duas: metade vai pro primeiro slot vazio. False se não deu."""
        s = self.slots[index]
        if s is None or s.count < 2 or None not in self.slots:
            return False
        half = self.take_half(index)
        self.slots[self.slots.index(None)] = half
        return True

    def quick_move(self, index: int, target: "Inventory") -> int:
        """Shift+clique: manda TODAS as pilhas do item desse slot pro outro inventário.
        O que não couber fica onde está. Devolve quantas unidades foram."""
        s = self.slots[index]
        if s is None:
            return 0
        item = s.item
        moved_total = 0
        for i, other in enumerate(self.slots):
            if other and other.item == item:
                left = target.add(item, other.count)
                moved_total += other.count - left
                self.slots[i] = Stack(item, left) if left else None
        return moved_total

    # ---- transferência entre dois painéis (baú/estação abertos, estilo Planet Crafter) ----
    def transfer(self, index: int, target: "Inventory", amount: int | None = None) -> int:
        """Manda `amount` unidades (None = a pilha inteira) do slot `index` pro `target`, que junta
        nas pilhas iguais e depois nos slots vazios. O que não couber fica no slot. Devolve quanto foi."""
        s = self.slots[index]
        if s is None:
            return 0
        want = s.count if amount is None else min(amount, s.count)
        moved = want - target.add(s.item, want)
        self.remove_from_slot(index, moved)
        return moved

    def transfer_all(self, target: "Inventory", items=None) -> int:
        """Manda tudo (ou só os itens em `items`) pro `target`, slot por slot, até onde couber.
        "Pegar tudo" e "Guardar tudo" do baú. Devolve quantas unidades foram."""
        moved = 0
        for i, s in enumerate(self.slots):
            if s is not None and (items is None or s.item in items):
                moved += self.transfer(i, target)
        return moved

    # ---- save (lista simples de [item, quantidade] ou None) -------------------
    def to_data(self) -> list:
        return [[s.item, s.count] if s else None for s in self.slots]

    @classmethod
    def from_data(cls, data: list) -> "Inventory":
        inv = cls(len(data))
        inv.slots = [Stack(d[0], d[1]) if d else None for d in data]
        return inv
