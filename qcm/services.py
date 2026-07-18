def parse_questions(texte_brut):
    """Parse a simple bulk text format into (question_texte, [(choix_texte, est_correct), ...]).

    Blocks are separated by a blank line; the first line of a block is the
    question, the following lines are its choices — a choice prefixed with
    "*" is the correct one. This avoids needing a JS-driven dynamic formset
    for what is otherwise a variable number of questions/choices per QCM.
    """
    blocs = [b.strip() for b in texte_brut.strip().split("\n\n") if b.strip()]
    questions = []
    for bloc in blocs:
        lignes = [ligne.strip() for ligne in bloc.splitlines() if ligne.strip()]
        if len(lignes) < 2:
            continue
        question_texte = lignes[0]
        choix = []
        for ligne in lignes[1:]:
            est_correct = ligne.startswith("*")
            texte_choix = ligne.lstrip("*").strip()
            if texte_choix:
                choix.append((texte_choix, est_correct))
        if choix:
            questions.append((question_texte, choix))
    return questions
