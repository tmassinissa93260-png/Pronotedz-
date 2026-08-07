"""Compatibilité : le module a déménagé dans `pdz.video.vie`.

Il faisait partie des outils de démonstration ; il fait maintenant partie du
programme, puisque la production s'en sert comme repli quand l'animation
payante est désactivée ou hors budget.
"""

from pdz.video.vie import Effets, Particule, animer

__all__ = ["Effets", "Particule", "animer"]
