"""Ponto de entrada: `uv run python -m game` (opcional: `--scale 2` pra forçar o zoom da janela)."""

import argparse

from game.app import App


def main() -> None:
    parser = argparse.ArgumentParser(description="Hesper · MVP v0.1")
    parser.add_argument("--scale", type=int, default=None, help="zoom inteiro da janela (padrão: o maior que cabe na tela)")
    args = parser.parse_args()
    App(scale=args.scale).run()


if __name__ == "__main__":
    main()
