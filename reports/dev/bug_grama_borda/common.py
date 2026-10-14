"""Helper do diagnóstico do bug da grama na borda (Verde, seed 598929664). Só scripts de investigação."""
import sys
from pathlib import Path

ROOT = Path("/Users/gabrieloliveira/personal_projects/hesper")
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools" / "dev"))

OUT = ROOT / "reports" / "dev" / "bug_grama_borda"
OUT.mkdir(parents=True, exist_ok=True)

import smoke  # noqa: E402  (módulo do smoke: só define coisas, o Bot é criado abaixo)
from game import config as C  # noqa: E402

SEED = 598929664


def setup(seed: int = SEED, size: int | None = None, base=None):
    """Cria um mundo headless com a seed, já no estágio Verde. Prints do smoke vão pra esta pasta."""
    smoke.OUT = OUT
    C.WORLD_SEED = seed
    bot = smoke.Bot()
    s = bot.state
    s.stage = C.GREEN_STAGE
    s.storm = 0.0
    return bot


def shot(bot, name: str) -> Path:
    path = OUT / name
    bot.app.screenshot(str(path))
    print(f"  screenshot: {path}")
    return path
