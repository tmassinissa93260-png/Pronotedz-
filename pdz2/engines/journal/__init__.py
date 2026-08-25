"""Journal de production — phase 12.

Le journal se relit depuis les contrats, il ne s'écrit pas au fil de l'eau :
un journal tenu à la main diverge dès la première reprise. Reconstruit, il ne
peut pas mentir.
"""

from pdz2.engines.journal.builder import JournalBuilder, JournalOutcome

__all__ = ["JournalBuilder", "JournalOutcome"]
