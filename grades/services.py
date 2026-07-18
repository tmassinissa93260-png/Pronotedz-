from decimal import Decimal

from academics.models import Matiere
from .models import Evaluation, Note


def moyenne_matiere(eleve, matiere, trimestre):
    """Weighted average (/20) of an élève's notes in one matière for one trimestre.

    Weighted by each évaluation's own coefficient_evaluation. Notes with a
    null valeur (absent) are excluded rather than counted as zero.
    """
    notes = Note.objects.filter(
        eleve=eleve,
        valeur__isnull=False,
        evaluation__matiere=matiere,
        evaluation__trimestre=trimestre,
        evaluation__classe=eleve.classe,
        evaluation__publie=True,
    ).select_related("evaluation")

    total_pondere = Decimal("0")
    total_coefficients = Decimal("0")
    for note in notes:
        note_sur_20 = note.valeur * Decimal("20") / note.evaluation.bareme
        poids = note.evaluation.coefficient_evaluation
        total_pondere += note_sur_20 * poids
        total_coefficients += poids

    if total_coefficients == 0:
        return None
    return round(total_pondere / total_coefficients, 2)


def moyenne_generale(eleve, trimestre):
    """Weighted average (/20) across all matières, weighted by CoefficientMatiere."""
    classe = eleve.classe
    matieres = Matiere.objects.filter(evaluations__classe=classe, evaluations__trimestre=trimestre).distinct()

    total_pondere = Decimal("0")
    total_coefficients = Decimal("0")
    for matiere in matieres:
        moyenne = moyenne_matiere(eleve, matiere, trimestre)
        if moyenne is None:
            continue
        coefficient_matiere = classe.coefficient_pour(matiere)
        poids = coefficient_matiere.coefficient if coefficient_matiere else Decimal("1")
        total_pondere += moyenne * poids
        total_coefficients += poids

    if total_coefficients == 0:
        return None
    return round(total_pondere / total_coefficients, 2)


def statistiques_classe_matiere(classe, matiere, trimestre):
    """Moyenne, min et max de la classe pour une matière/trimestre donnés.

    Returns a dict {moyenne, min, max} or None if no student has a grade yet.
    """
    moyennes = [
        m for m in (moyenne_matiere(eleve, matiere, trimestre) for eleve in classe.eleves.all())
        if m is not None
    ]
    if not moyennes:
        return None
    return {
        "moyenne": round(sum(moyennes) / len(moyennes), 2),
        "min": min(moyennes),
        "max": max(moyennes),
    }


def rang_classe(eleve, trimestre):
    """1-based rank of eleve's moyenne_generale among their classmates, or None."""
    classe = eleve.classe
    moyennes = []
    for camarade in classe.eleves.all():
        moyenne = moyenne_generale(camarade, trimestre)
        if moyenne is not None:
            moyennes.append((camarade.pk, moyenne))

    moyennes.sort(key=lambda item: item[1], reverse=True)
    for rang, (eleve_pk, _) in enumerate(moyennes, start=1):
        if eleve_pk == eleve.pk:
            return rang, len(moyennes)
    return None, len(moyennes)
