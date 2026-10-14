"""Contador de desempenho no canto de baixo à esquerda (F5 liga/desliga, pedido do dono).

Mostra o FPS e, mais importante, os ms de TRABALHO do quadro (update + desenho, sem a espera do vsync), com a
média e o pior quadro da última janela de C.PERF_WINDOW_S. Como o jogo trava em 60 FPS, o FPS sozinho só cai
quando já estourou; os ms mostram a folga até o orçamento de 16,7 ms (verde, amarelo, vermelho).
"""

from __future__ import annotations

import pygame

from game import config as C


class PerfMeter:
    def __init__(self) -> None:
        self.visible = C.PERF_METER_ON
        self._acc_t = 0.0                 # tempo de relógio acumulado na janela (s)
        self._frames = 0
        self._work: list[float] = []      # ms de trabalho de cada quadro da janela
        self.fps = 0.0
        self.avg_ms = 0.0
        self.worst_ms = 0.0
        self._font: pygame.font.Font | None = None

    def toggle(self) -> None:
        self.visible = not self.visible

    def add(self, dt: float, work_ms: float) -> None:
        """Um quadro: `dt` = tempo de relógio desde o anterior (s), `work_ms` = trabalho dele (ms)."""
        self._acc_t += dt
        self._frames += 1
        self._work.append(work_ms)
        if self._acc_t >= C.PERF_WINDOW_S - 1e-9:      # (30 × 1/60 em float dá 0,4999...)
            self.fps = self._frames / self._acc_t
            self.avg_ms = sum(self._work) / len(self._work)
            self.worst_ms = max(self._work)
            self._acc_t, self._frames, self._work = 0.0, 0, []

    def text(self) -> str:
        avg = f"{self.avg_ms:.1f}".replace(".", ",")
        worst = f"{self.worst_ms:.1f}".replace(".", ",")
        return f"{round(self.fps)} FPS · {avg} ms (pior {worst})"

    def color(self) -> str:
        ok, warn = C.PERF_MS_LEVELS
        return C.C_OK if self.avg_ms <= ok and self.worst_ms <= C.FRAME_BUDGET_MS else \
            ("#f2c46d" if self.avg_ms <= warn else "#ff6a55")

    def draw(self, window: pygame.Surface) -> None:
        """Direto na janela (por cima de tudo, fora da escala da UI), no canto de baixo à esquerda."""
        if not self.visible or self._font is None and not self._load_font():
            return
        label = self._font.render(self.text(), False, pygame.Color(self.color()))
        pad = 4
        box = pygame.Surface((label.get_width() + 2 * pad, label.get_height() + 2 * pad), pygame.SRCALPHA)
        box.fill((10, 8, 20, 170))
        box.blit(label, (pad, pad))
        window.blit(box, (16, window.get_height() - box.get_height() - 16))   # longe da borda (o canto da janela corta)

    def _load_font(self) -> bool:
        from game.assets import load_font
        self._font = load_font("Silkscreen-Regular.ttf", 16, 20)
        return self._font is not None
