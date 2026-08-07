"""Compatibilité : la vérification des clés a déménagé dans `pdz.cles`.

    pdz cles                      ← à utiliser
    python -m tools.verifier_cles ← continue de marcher
"""

from pdz.cles import main

__all__ = ["main"]

if __name__ == "__main__":
    raise SystemExit(main())
