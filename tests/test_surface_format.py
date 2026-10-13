"""Nenhuma superfície do jogo no formato padrão (o da janela): ver game/surfaces.py.

No driver dummy dos testes o formato padrão não tem alfa, então um bug desses só aparece na janela de
verdade do macOS (o tools/dev/real_video_check.py confere lá). Aqui só garante que ninguém volta a
escrever `pygame.Surface(size)` sem dizer se quer SRCALPHA ou opaca.
"""

import ast
from pathlib import Path

import pygame

from game.surfaces import OPAQUE_MASKS, opaque

GAME = Path(__file__).resolve().parents[1] / "game"


def default_format_surfaces() -> list[str]:
    found = []
    for path in sorted(GAME.glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(), str(path))):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            name = f.attr if isinstance(f, ast.Attribute) else f.id if isinstance(f, ast.Name) else None
            if name == "Surface" and len(node.args) + len(node.keywords) < 2:
                found.append(f"{path.name}:{node.lineno}")
    return found


def test_no_surface_in_the_window_default_format():
    assert default_format_surfaces() == []


def test_opaque_has_no_alpha_channel():
    s = opaque((4, 3))
    assert s.get_size() == (4, 3) and s.get_bitsize() == 32
    assert s.get_masks() == OPAQUE_MASKS and not s.get_flags() & pygame.SRCALPHA
