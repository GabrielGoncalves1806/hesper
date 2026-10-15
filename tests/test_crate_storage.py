"""v0.6 M1 · Task 2: a caixa de saque guarda item e desmonta vazia; o contêiner guarda mas não desmonta."""

import json

from game import config as C
from game import map_view as MV
from game import save
from game.inventory import Inventory, Stack
from game.systems import Controls, GameState
from game.wrecks import ContainerSpot, Crate
from tests.helpers import give


def first_crate(s):
    return s.crates[s.world.wrecks[0].crate]


def stand_next_to(s, crate):
    cx, cy = crate.tile
    s.player.x, s.player.y = (cx + 0.5) * C.TILE, (cy + 1) * C.TILE + 8


def emptied(s):
    """Abre a caixa e esvazia (inventário esvaziado antes, pra caber tudo)."""
    crate = first_crate(s)
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.open_crate(crate)
    s.crate_take(crate)
    s.inventory.slots[:] = [None] * len(s.inventory)
    s.pop_events()
    stand_next_to(s, crate)
    return crate


def hold(s, crate, seconds):
    t = 0.0
    while t < seconds:
        s.update(0.05, Controls(dismantle=crate))
        t += 0.05


def test_opened_crate_stores_items_closed_one_does_not():
    s = GameState(7)
    crate = emptied(s)
    give(s, iron=10)
    i = next(k for k, x in enumerate(s.inventory.slots) if x and x.item == "iron")
    crate.opened = False
    assert s.crate_put(crate, i, None) == 0
    crate.opened = True
    assert s.crate_put(crate, i, 4) == 4 and crate.storage.count("iron") == 4 and s.inventory.count("iron") == 6
    assert s.crate_put(crate, i, None) == 6 and s.inventory.count("iron") == 0


def test_container_stores_items_but_never_dismantles():
    s = GameState(7)
    spot = ContainerSpot(*s.player.tile)
    box = Crate(spot, Inventory(C.CRATE_SLOTS), opened=True)
    s.surface.containers[spot.crate] = box
    give(s, ice=3)
    assert s.crate_put(box, next(k for k, x in enumerate(s.inventory.slots) if x and x.item == "ice"), None) == 3
    box.storage.clear()
    assert not s.can_dismantle(box) and not s.dismantle_crate(box)


def test_dismantle_empty_crate_returns_iron_turns_tile_to_sand_and_removes_it():
    s = GameState(7)
    crate = emptied(s)
    tile = crate.tile
    hold(s, crate, C.DISMANTLE_HOLD + 0.2)
    assert s.inventory.count("iron") == C.CRATE_DISMANTLE_RETURN["iron"] == 3
    assert s.world.get(*tile) == C.SAND and tile not in s.crates
    assert tile in s.surface.removed_crates and ("dismantle", "crate", tile) in s.events


def test_crate_with_item_does_not_dismantle():
    s = GameState(7)
    crate = emptied(s)
    crate.storage.add("ice", 2)
    hold(s, crate, C.DISMANTLE_HOLD + 0.2)
    assert crate.tile in s.crates and ("crate_not_empty",) in s.events and s.inventory.count("iron") == 0


def test_full_inventory_blocks_crate_dismantle():
    s = GameState(7)
    crate = emptied(s)
    s.inventory.slots[:] = [Stack("ice", 50) for _ in s.inventory.slots]
    hold(s, crate, C.DISMANTLE_HOLD + 0.2)
    assert crate.tile in s.crates and ("inv_full",) in s.events


def test_too_far_from_crate_no_dismantle():
    s = GameState(7)
    crate = emptied(s)
    s.player.x += 10 * C.TILE
    hold(s, crate, C.DISMANTLE_HOLD + 0.2)
    assert crate.tile in s.crates


def test_save_roundtrip_keeps_stored_item_and_removed_crate_stays_gone():
    s = save.new_state()
    a, b = s.world.wrecks[0], s.world.wrecks[1]
    ca = s.crates[a.crate]
    s.open_crate(ca)
    ca.storage.add("silicon", 7)
    cb = s.crates[b.crate]
    cb.storage = Inventory(C.CRATE_SLOTS)
    cb.opened = True
    s.player.x, s.player.y = (b.crate[0] + 0.5) * C.TILE, (b.crate[1] + 1) * C.TILE + 8
    assert s.dismantle_crate(cb)
    data = json.loads(json.dumps(save.state_to_dict(s)))
    loaded = save.state_from_dict(data)
    assert loaded.crates[a.crate].storage.count("silicon") == s.crates[a.crate].storage.count("silicon")
    assert b.crate not in loaded.crates and loaded.world.get(*b.crate) == C.SAND
    data["layers"]["surface"].pop("removed_crates")          # save sem o campo: nenhuma caixa removida
    again = save.state_from_dict(data)
    assert b.crate in again.crates


def test_map_view_wreck_without_crate_shows_empty():
    s = GameState(7)
    crate = emptied(s)
    s.dismantle_crate(crate)
    s.surface.explored.reveal_rect(0, 0, s.world.width, s.world.height)
    entries = MV.map_entries(s, "surface")
    assert any(e.category == "wreck_empty" for e in entries)
