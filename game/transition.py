"""Transição gradual de estágio: o planeta muda tile por tile, como uma mancha se espalhando.

Ideia em uma frase: nos últimos 35% da barra de progresso até o próximo estágio, cada tile
"vira" pro visual do próximo estágio quando a frente da mancha passa por ele. A frente avança
a partir da base e das máquinas, e a distância de cada tile até elas é "amassada" por ruído pra
borda ficar orgânica. Resultado: a mancha começa perto de onde o jogador está trabalhando e vai
se espalhando pras bordas do mapa.

    progresso do estágio  0% ........................ 65% ............ 100% (limiar)
                                                       |<-- janela -->|
    tile perto da base                                   vira aqui
    tile na borda do mapa                                          vira aqui

Tudo aqui é Python puro (sem pygame), pra dar pra testar. O render.py só pergunta
`StageMap.stage_at(tx, ty)` pra saber com qual estágio desenhar cada tile.

Garantias (testadas em tests/test_transition.py):
- determinística: mesma entrada, mesma resposta;
- monotônica: com o Ti subindo (e as fontes só crescendo), um tile convertido nunca desconverte;
- antes da janela nada muda; no limiar o estágio novo vale pro mapa inteiro.
"""

import math

from game import config as C
from game.systems import stage_for_ti, stage_progress
from game.world import hash01, value_noise

# A base é sempre uma fonte da mancha: o centro da cápsula (em tiles), no meio da superfície.
BASE_SOURCE = (C.BASE_TILE[0], C.POD_TILES[0][1])


# ---------------------------------------------------------------------------
# Em que ponto da janela de transição estamos
# ---------------------------------------------------------------------------
def window_progress(ti: float, biomass: float = 0.0) -> tuple[int, float]:
    """(estágio atual, quanto da janela de transição já andou, de 0 a 1).

    Ex.: com Ti 9.000 estamos no estágio 1 com 90% da barra; a janela começa em 65%,
    então andamos (0,90 - 0,65) / 0,35 = ~71% dela. No último estágio não tem janela (0).
    v0.8 M1: com a biomassa, a janela anda pelo gargalo (o mesmo progresso do HUD).
    """
    stage = stage_for_ti(ti, biomass)
    nxt, fraction, _, _ = stage_progress(ti, biomass)
    if nxt is None:
        return stage, 0.0
    start = 1.0 - C.TRANSITION_WINDOW
    return stage, max(0.0, (fraction - start) / C.TRANSITION_WINDOW)


def window_step(ti: float, biomass: float = 0.0) -> tuple[int, int]:
    """Mesma coisa, mas em "degraus" inteiros (0 a TRANSITION_STEPS - 1).

    O visual só muda quando o degrau muda (a cada 1% da janela). Isso deixa o desenho
    cacheável: enquanto o degrau não muda, o estágio de cada tile também não muda.
    """
    stage, progress = window_progress(ti, biomass)
    return stage, min(C.TRANSITION_STEPS - 1, int(progress * C.TRANSITION_STEPS))


# ---------------------------------------------------------------------------
# Quando cada tile vira
# ---------------------------------------------------------------------------
def effective_distance(x: int, y: int, sources, seed: int = C.WORLD_SEED) -> float:
    """Distância (em tiles) até a fonte mais perto, "amassada" por ruído.

    - `wobble`: ruído suave (manchas grandes) que estica ou encolhe a distância em até ±metade.
      É ele que faz a borda da mancha ter dedos e baías em vez de ser um círculo.
    - `grain`: um sorteio por tile, pequeno, que esfarela a fronteira (os tiles da borda não viram
      todos juntos numa linha reta).
    """
    d = min(math.hypot(x - sx, y - sy) for sx, sy in sources)
    wobble = value_noise(x * C.TRANSITION_NOISE_SCALE, y * C.TRANSITION_NOISE_SCALE, seed + 51) - 0.5
    grain = hash01(x, y, seed + 52) - 0.5
    return max(0.0, d * (1 + C.TRANSITION_WOBBLE * wobble) + C.TRANSITION_GRAIN * grain)


def front_distance(progress: float) -> float:
    """Até quantos tiles (de distância efetiva) a mancha já chegou, com a janela em `progress` (0 a 1).

    Duas partes somadas:
    - uma reta (`NEAR * progress`): perto da base a mancha anda devagar e constante,
      então dá tempo de ver ela nascer e crescer em volta da cápsula e das máquinas;
    - uma curva bem fechada (`FAR * progress^8`): quase nada no começo e dispara no fim,
      levando a mancha até as bordas do mapa antes do limiar.
    Com os valores do config: 25% → ~4 tiles, 60% → ~11, 90% → ~77, 99% → ~152 (o canto do deserto fica a ~136).
    Tile mais longe que a frente no último degrau vira junto com o limiar.
    """
    return C.TRANSITION_FRONT_NEAR * progress + C.TRANSITION_FRONT_FAR * progress ** C.TRANSITION_FRONT_POWER


def tile_stage(x: int, y: int, ti: float, sources, seed: int = C.WORLD_SEED, biomass: float = 0.0) -> int:
    """Número do estágio (1, 2, 3) com que o tile (x, y) deve ser desenhado com esse Ti.

    `sources` são os tiles de onde a mancha nasce: a base e toda máquina que já foi colocada.
    """
    stage, step = window_step(ti, biomass)
    if step > 0 and effective_distance(x, y, sources, seed) < front_distance(step / C.TRANSITION_STEPS):
        return stage + 1
    return stage


# ---------------------------------------------------------------------------
# Cache por pedaço do mapa (o render pergunta isso centenas de vezes por frame)
# ---------------------------------------------------------------------------
class StageMap:
    """Guarda o estágio visual de cada tile em pedaços de 16×16, calculados só quando alguém pede.

    - a distância efetiva de cada tile só depende das fontes: é recalculada quando
      uma máquina nova é colocada;
    - o estágio de cada tile depende do degrau: é recalculado quando o degrau muda (1% da janela).
    Fora da janela de transição nem olha os pedaços: o mapa todo está no mesmo estágio.
    """

    CHUNK = 16

    def __init__(self, seed: int = C.WORLD_SEED):
        self.seed = seed
        self.stage = 1                # estágio "oficial" (pelo Ti)
        self.step = 0                 # degrau atual da janela (0 = nada convertido)
        self.progress = 0.0           # progresso contínuo da janela (pra clima e luz)
        self._sources: tuple = ()
        self._distances: dict[tuple[int, int], list[float]] = {}
        self._stages: dict[tuple[int, int], bytes] = {}

    def update(self, ti: float, sources, biomass: float = 0.0) -> None:
        """Chamar uma vez por frame. Só joga cache fora se as fontes ou o degrau mudaram."""
        sources = tuple(sorted(set(sources)))
        if sources != self._sources:
            self._sources = sources
            self._distances.clear()
            self._stages.clear()
        stage, self.progress = window_progress(ti, biomass)
        step = min(C.TRANSITION_STEPS - 1, int(self.progress * C.TRANSITION_STEPS))
        if (stage, step) != (self.stage, self.step):
            self.stage, self.step = stage, step
            self._stages.clear()

    @property
    def next_stage(self) -> int:
        """Estágio que está "entrando" (igual ao atual se não tem transição rolando)."""
        return self.stage + 1 if self.step > 0 else self.stage

    def stage_at(self, x: int, y: int) -> int:
        if self.step == 0:
            return self.stage
        key = (x // self.CHUNK, y // self.CHUNK)
        chunk = self._stages.get(key)
        if chunk is None:
            chunk = self._stages[key] = self._build_chunk(key)
        return chunk[(y % self.CHUNK) * self.CHUNK + x % self.CHUNK]

    def _build_chunk(self, key: tuple[int, int]) -> bytes:
        distances = self._distances.get(key)
        if distances is None:
            x0, y0 = key[0] * self.CHUNK, key[1] * self.CHUNK
            distances = self._distances[key] = [
                effective_distance(x0 + i, y0 + j, self._sources, self.seed)
                for j in range(self.CHUNK) for i in range(self.CHUNK)
            ]
        front = front_distance(self.step / C.TRANSITION_STEPS)
        return bytes(self.stage + 1 if d < front else self.stage for d in distances)
