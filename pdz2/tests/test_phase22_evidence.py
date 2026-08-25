"""Ce que la commande demande réellement au générateur d'images.

Le run #7 a produit une vidéo techniquement valide et visuellement mauvaise.
Le diagnostic facile — « le fournisseur d'images est faible » — était faux.
Trois défauts du dépôt suffisaient à expliquer les images génériques, et
aucun n'est dans le modèle :

1. **La preuve n'était pas transmise.** `ShotSpec` portait `claim_id` et
   `evidence_required`, recopiés du brief ; `ImageSpec` ne les avait pas. Le
   générateur recevait un sujet, jamais une preuve.
2. **Les calques étaient vides.** Leurs descriptions étaient des constantes
   dépendant du seul cadrage. Un fournisseur reçoit un appel par calque : sur
   un plan large, trois demandes sur quatre ne portaient aucune matière.
3. **La composition était inversée.** Le calque le plus lointain était peint
   en dernier. Invisible avec le moteur local, qui dessine des calques
   transparents ; fatal avec un moteur génératif, qui rend des images opaques.

Ces tests tiennent les trois corrections, et le quatrième tient la
dé-duplication du prompt.
"""

from __future__ import annotations

from pdz2.contracts.enums import Framing
from pdz2.contracts.visual import LayerRole
from pdz2.engines.imagery import layers_for


class TestLaPreuveTraverseLaFrontiere:
    """Ce que la narration exige doit atteindre celui qui fabrique l'image."""

    def test_the_image_contract_carries_what_must_be_proven(self, tmp_path) -> None:
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        specs = {spec.shot_id: spec for spec in episode.image_specs}
        assert specs, "aucune spécification d'image produite"

        demonstratifs = [
            spec for spec in specs.values() if spec.claim_id is not None
        ]
        assert demonstratifs, "aucune image ne démontre quoi que ce soit"
        for spec in demonstratifs:
            assert spec.evidence_required, (
                f"{spec.shot_id} démontre {spec.claim_id} sans dire ce qui doit "
                "être visible"
            )

    def test_the_evidence_matches_the_shot_it_comes_from(self, tmp_path) -> None:
        """Recopié du plan, pas réinventé par le compilateur d'images."""
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        plans = {shot.shot_id: shot for shot in episode.graph.shots}
        for spec in episode.image_specs:
            shot = plans[spec.shot_id]
            assert spec.claim_id == shot.claim_id
            assert spec.evidence_required == shot.evidence_required


class TestLesCalquesPortentLaScene:
    """Quatre appels distincts, quatre demandes qui disent quelque chose."""

    SUJET = "la came pousse le poussoir de huit millimètres, vue en coupe"

    def test_no_layer_is_asked_for_nothing(self) -> None:
        for framing in (Framing.WIDE, Framing.MEDIUM, Framing.CUTAWAY_DIAGRAM):
            for calque in layers_for(framing, self.SUJET):
                assert self.SUJET in calque.description, (
                    f"{framing.value}/{calque.role.value} : demande sans matière"
                )

    def test_the_layers_stay_distinguishable(self) -> None:
        """Sans quoi quatre appels rendent quatre fois la même image."""
        descriptions = [c.description for c in layers_for(Framing.WIDE, self.SUJET)]
        assert len(set(descriptions)) == len(descriptions)

    def test_the_depth_count_still_follows_the_framing(self) -> None:
        """Le parallaxe a besoin de plans séparés ; une coupe n'en a qu'un."""
        assert len(layers_for(Framing.CUTAWAY_DIAGRAM, self.SUJET)) == 1
        assert len(layers_for(Framing.WIDE, self.SUJET)) == 4
        assert len(layers_for(Framing.MEDIUM, self.SUJET)) == 2

    def test_an_empty_subject_degrades_without_breaking(self) -> None:
        for calque in layers_for(Framing.WIDE):
            assert calque.description.strip()
            assert "  " not in calque.description


class TestLOrdreDeComposition:
    """Le fond se peint en premier. Le contraire efface le sujet."""

    def test_layers_are_painted_back_to_front(self, tmp_path) -> None:
        """Trois carrés opaques : seul le plus proche doit rester visible.

        Ce test emploie de vraies images opaques, comme celles que rend un
        moteur génératif — c'est précisément ce que le moteur local, qui
        dessine sur fond transparent, ne pouvait pas révéler.
        """
        from PIL import Image

        from pdz2.providers.fal import _composer
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        spec = next(s for s in episode.image_specs if len(s.layers) >= 3)

        couleurs = {}
        chemins = {}
        for index, calque in enumerate(sorted(spec.layers, key=lambda c: c.depth)):
            couleur = (10 + index * 60, 20, 30)
            couleurs[calque.role] = couleur
            chemin = tmp_path / f"{calque.role.value}.png"
            Image.new("RGB", (spec.resolution.width, spec.resolution.height),
                      couleur).save(chemin)
            chemins[calque.role] = chemin

        cible = tmp_path / "composite.png"
        _composer(chemins, cible, spec)

        proche = max(spec.layers, key=lambda c: c.depth)
        rendu = Image.open(cible).convert("RGB").getpixel((5, 5))
        assert rendu == couleurs[proche.role], (
            f"le calque visible est {rendu}, on attendait celui de profondeur "
            f"{proche.depth} ({couleurs[proche.role]}) — l'ordre est inversé"
        )

    def test_the_convention_matches_the_parallax_renderer(self) -> None:
        """Profondeur haute = calque proche. C'est le 2.5D qui l'a fixée."""
        calques = layers_for(Framing.WIDE, "peu importe")
        par_role = {c.role: c.depth for c in calques}
        assert par_role[LayerRole.SKY] < par_role[LayerRole.BACKGROUND]
        assert par_role[LayerRole.BACKGROUND] < par_role[LayerRole.SUBJECT]
        assert par_role[LayerRole.SUBJECT] < par_role[LayerRole.FOREGROUND]


class TestLePromptNeSeRepetePlus:
    """Une consigne répétée n'est pas une consigne appuyée."""

    def test_the_bible_is_stated_once(self, tmp_path) -> None:
        from pdz2.contracts.visual import VisualBible
        from pdz2.providers.prompting import image_prompt
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        bible: VisualBible = episode.bible
        spec = episode.image_specs[0]
        prompt = image_prompt(spec, bible)

        for fragment in (bible.lighting, bible.texture, bible.environment):
            assert prompt.count(fragment) <= 1, (
                f"« {fragment[:40]}… » apparaît {prompt.count(fragment)} fois"
            )

    def test_what_must_be_proven_comes_first(self, tmp_path) -> None:
        """Un moteur qui lit d'abord le style traite le mécanisme en dernier."""
        from pdz2.providers.prompting import image_prompt
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        spec = next(s for s in episode.image_specs if s.evidence_required)
        prompt = image_prompt(spec, episode.bible)

        assert prompt.startswith("L'image doit rendre visible")
        assert spec.evidence_required.rstrip(".") in prompt

