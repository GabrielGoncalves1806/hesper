"""v0.8 M4 · Save: Microscópio e Centrífuga voltam com conteúdo e timer; slots sujos carregam vazios."""

from game import config as C
from game import save
from game.inventory import Stack
from game.systems import Machine


def _mic_with_content() -> Machine:
    m = Machine(C.MICROSCOPE, 7, 8)
    m.storage.slots[C.MIC_ICE_SLOT] = Stack("ice", 3)
    m.storage.slots[C.MIC_OUT_SLOTS["sample_basic"]] = Stack("sample_basic", 2)
    m.storage.slots[C.MIC_OUT_SLOTS["sample_rare"]] = Stack("sample_rare", 1)
    m.timer = 7.5
    return m


def _cent_with_content() -> Machine:
    m = Machine(C.CENTRIFUGE, 9, 8)
    m.storage.slots[C.CENT_ALGAE_SLOT] = Stack("algae", 2)
    m.storage.slots[C.CENT_SAMPLE_SLOT] = Stack("sample_mutant", 1)
    m.storage.slots[C.CENT_OUT_SLOTS["plant_3"]] = Stack("plant_3", 1)
    m.timer = 12.0
    return m


def test_microscope_roundtrip():
    m = _mic_with_content()
    data = save.machine_to_dict(m)
    assert data["timer"] == 7.5
    back = save.machine_from_dict(data)
    assert back.storage.slots == m.storage.slots and back.timer == 7.5


def test_centrifuge_roundtrip():
    m = _cent_with_content()
    data = save.machine_to_dict(m)
    assert data["timer"] == 12.0
    back = save.machine_from_dict(data)
    assert back.storage.slots == m.storage.slots and back.timer == 12.0


def test_dirty_slots_load_empty_and_timer_is_clamped():
    # microscópio: ferro na entrada, amostra rara no slot da simples, gelo na saída
    mic = save.machine_from_dict({"kind": C.MICROSCOPE, "tx": 1, "ty": 1, "rotation": 0, "timer": 999,
                                  "storage": [["iron", 4], ["sample_rare", 1], ["ice", 2], ["sample_basic", 1]]})
    assert mic.storage.slots[C.MIC_ICE_SLOT] is None and mic.storage.slots[1] is None
    assert mic.storage.slots[2] is None and mic.storage.slots[3] is None
    assert mic.timer == C.MICROSCOPE_TIME
    # centrífuga: ferro na alga, gelo na amostra, planta certa no slot certo e gelo na saída
    cent = save.machine_from_dict({"kind": C.CENTRIFUGE, "tx": 1, "ty": 1, "rotation": 0, "timer": -5,
                                   "storage": [["iron", 1], ["ice", 3], ["plant_1", 1], ["ice", 1], ["plant_1", 1]]})
    assert cent.storage.slots[0] is None and cent.storage.slots[1] is None
    assert cent.storage.slots[2] == Stack("plant_1", 1)
    assert cent.storage.slots[3] is None and cent.storage.slots[4] is None
    assert cent.timer == 0.0
    assert save.machine_from_dict({"kind": C.MICROSCOPE, "tx": 1, "ty": 1, "rotation": 0}).storage.is_empty()


def test_full_state_roundtrip_keeps_diagram_samples_and_machines():
    g = save.new_state(3)
    g.blueprints.add("microscope")
    g.inventory.slots[0] = Stack("sample_rare", 2)
    chest = Machine("chest", 60, 60)
    chest.storage.slots[1] = Stack("sample_mutant", 5)
    g.machines.extend([chest, _mic_with_content(), _cent_with_content()])
    back = save.state_from_dict(save.migrate(save.state_to_dict(g)))
    assert "microscope" in back.blueprints
    assert back.inventory.slots[0] == Stack("sample_rare", 2)
    assert next(m for m in back.machines if m.kind == "chest").storage.slots[1] == Stack("sample_mutant", 5)
    mic = next(m for m in back.machines if m.is_microscope)
    cent = next(m for m in back.machines if m.is_centrifuge)
    assert mic.timer == 7.5 and mic.storage.count("ice") == 3 and mic.storage.count("sample_basic") == 2
    assert cent.timer == 12.0 and cent.storage.count("algae") == 2 and cent.storage.count("plant_3") == 1
