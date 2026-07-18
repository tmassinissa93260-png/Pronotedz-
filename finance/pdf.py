import io

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def generer_recu_pdf(paiement):
    """Renders a payment receipt to a PDF (in-memory buffer)."""
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elements = []

    eleve = paiement.facture.eleve
    etablissement = eleve.classe.annee_scolaire.etablissement
    elements.append(Paragraph(etablissement.nom if etablissement else "Établissement", styles["Title"]))
    elements.append(Paragraph(f"Reçu de paiement — {paiement.numero_recu}", styles["Heading2"]))
    elements.append(Spacer(1, 0.3 * cm))
    elements.append(
        Paragraph(
            f"Élève : {eleve.user.get_full_name()} — Classe : {eleve.classe} — Matricule : {eleve.matricule}",
            styles["Normal"],
        )
    )
    elements.append(Spacer(1, 0.5 * cm))

    data = [
        ["Frais", "Date de paiement", "Mode de paiement", "Référence", "Montant"],
        [
            paiement.facture.frais.libelle,
            paiement.date_paiement.strftime("%d/%m/%Y"),
            paiement.get_mode_paiement_display(),
            paiement.reference or "—",
            f"{paiement.montant} DA",
        ],
    ]
    table = Table(data, repeatRows=1, colWidths=[4.5 * cm, 3 * cm, 3 * cm, 3.5 * cm, 3 * cm])
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2f5fa8")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 0.6 * cm))
    elements.append(
        Paragraph(f"<b>Solde restant sur cette facture : {paiement.facture.montant_restant} DA</b>", styles["Normal"])
    )

    doc.build(elements)
    buffer.seek(0)
    return buffer
