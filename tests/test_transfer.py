"""Transferência entre painéis (estilo Planet Crafter): pilha inteira, 1 unidade, cheio, Pegar/Guardar tudo."""

from game import config as C
from game.inventory import Inventory, Stack


def test_left_click_moves_the_whole_stack():
    inv, box = Inventory(16), Inventory(24)
    inv.slots[3] = Stack("iron", 37)
    assert inv.transfer(3, box) == 37
    assert inv.slots[3] is None and box.count("iron") == 37


def test_right_click_moves_one():
    inv, box = Inventory(16), Inventory(24)
    inv.slots[0] = Stack("ice", 5)
    assert inv.transfer(0, box, 1) == 1
    assert inv.slots[0].count == 4 and box.slots[0] == Stack("ice", 1)
    box.transfer(0, inv, 1)                         # e volta, juntando na pilha que já existe
    assert inv.slots[0].count == 5 and box.is_empty()


def test_transfer_joins_existing_stacks_first():
    inv, box = Inventory(16), Inventory(24)
    box.slots[7] = Stack("iron", 45)
    inv.slots[0] = Stack("iron", 20)
    assert inv.transfer(0, box) == 20
    assert box.slots[7].count == 50 and box.slots[0] == Stack("iron", 15)


def test_full_target_keeps_the_rest_in_place():
    inv, box = Inventory(16), Inventory(2)
    box.slots = [Stack("silicon", 50), Stack("iron", 48)]
    inv.slots[2] = Stack("iron", 10)
    assert inv.transfer(2, box) == 2
    assert inv.slots[2].count == 8 and box.slots[1].count == 50
    assert inv.transfer(2, box) == 0 and inv.slots[2].count == 8          # sem espaço nenhum
    assert inv.transfer(5, box) == 0                                      # slot vazio


def test_machine_stacks_move_up_to_5():
    inv, box = Inventory(16), Inventory(1)
    inv.slots[0] = Stack("drone", 5)
    box.slots[0] = Stack("drone", 3)
    assert inv.transfer(0, box) == 2 and inv.slots[0].count == 3


def test_take_all_moves_what_fits():
    box, inv = Inventory(24), Inventory(2)
    box.slots[0] = Stack("iron", 50)
    box.slots[1] = Stack("ice", 20)
    box.slots[2] = Stack("o2", 1)
    assert box.transfer_all(inv) == 70
    assert inv.counts() == {"iron": 50, "ice": 20} and box.counts() == {"o2": 1}


def test_store_all_only_resources():
    inv, box = Inventory(16), Inventory(24)
    inv.slots[0] = Stack("drone", 2)               # hotbar: máquinas e drones ficam
    inv.slots[1] = Stack("iron", 12)               # recurso na hotbar vai
    inv.slots[2] = Stack("chest", 1)
    inv.slots[9] = Stack("silicon", 30)
    inv.slots[10] = Stack("ice", 4)
    assert inv.transfer_all(box, C.RESOURCES) == 46
    assert inv.counts() == {"drone": 2, "chest": 1}
    assert box.counts() == {"iron": 12, "silicon": 30, "ice": 4}
