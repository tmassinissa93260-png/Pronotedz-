import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from academics.models import Etablissement


def generer_bulletin_pdf(eleve, trimestre, contexte):
    """Renders a trimestre report card to a PDF (in-memory buffer)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elements = []

    etablissement = Etablissement.get_solo()
    elements.append(Paragraph(etablissement.nom if etablissement else "Établissement", styles["Title"]))
    elements.append(Paragraph(f"Bulletin — {trimestre}", styles["Heading2"]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(
        Paragraph(
            f"Élève : {eleve.user.get_full_name()} — Classe : {eleve.classe} — Matricule : {eleve.matricule}",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 0.5 * cm))

    data = [["Matière", "Coef.", "Moyenne élève", "Moyenne classe", "Min", "Max", "Appréciation"]]
    for ligne in contexte["lignes"]:
        stats = ligne["stats_classe"]
        data.append(
            [
                str(ligne["matiere"]),
                str(ligne["coefficient"].coefficient) if ligne["coefficient"] else "-",
                str(ligne["moyenne"]) if ligne["moyenne"] is not None else "—",
                str(stats["moyenne"]) if stats else "—",
                str(stats["min"]) if stats else "—",
                str(stats["max"]) if stats else "—",
                ligne["appreciation"] or "",
            ]
        )

    table = Table(data, repeatRows=1, colWidths=[3.2 * cm, 1.5 * cm, 2.3 * cm, 2.3 * cm, 1.5 * cm, 1.5 * cm, 4.5 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f5fa8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f4f6f9")]),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 0.6 * cm))

    moyenne_generale = contexte["moyenne_generale"]
    rang, effectif = contexte["rang"], contexte["effectif"]
    elements.append(
        Paragraph(
            f"<b>Moyenne générale : {moyenne_generale if moyenne_generale is not None else '—'} / 20</b>"
            + (f" — Rang : {rang} / {effectif}" if rang else ""),
            styles["Normal"],
        )
    )

    if contexte["appreciation_generale"] and contexte["appreciation_generale"].texte:
        elements.append(Spacer(1, 0.4 * cm))
        elements.append(Paragraph("<b>Appréciation générale</b>", styles["Normal"]))
        elements.append(Paragraph(contexte["appreciation_generale"].texte, styles["Normal"]))

    doc.build(elements)
    buffer.seek(0)
    return buffer
