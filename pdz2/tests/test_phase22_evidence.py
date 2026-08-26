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



# ------------------------------------------- le mouvement demandé doit se voir


class TestLesAmplitudesDeMouvement:
    """Un mouvement trop lent n'est pas un mouvement discret : c'est une image fixe.

    Le run #7 a été décrit par son auteur comme dépourvu d'animation, alors que
    sept plans sur huit avaient une caméra en mouvement et que l'observateur les
    déclarait conformes. Le calcul le confirmait : un panoramique parcourait
    trente-quatre pixels sur un plan de cinq secondes, soit 0,2 pixel par image.

    Deux causes, toutes deux dans le renderer :

    * l'amplitude de **parallaxe** servait d'amplitude de **caméra**, alors
      qu'un écart de 9 % entre calques est important quand un déplacement de
      caméra de 9 % ne l'est pas ;
    * le décalage valait `offset × depth`, donc le calque de profondeur 0,0
      restait strictement immobile.
    """

    def test_camera_travel_is_not_the_parallax_amplitude(self) -> None:
        """Deux grandeurs différentes, deux constantes différentes."""
        from pdz2.renderers.deterministic import MAX_CAMERA_TRAVEL, MAX_PARALLAX_SHIFT

        assert MAX_CAMERA_TRAVEL > MAX_PARALLAX_SHIFT * 2, (
            "le parcours caméra est de nouveau confondu avec l'écart de parallaxe"
        )

    def test_a_pan_crosses_enough_of_the_frame_to_be_seen(self) -> None:
        """Le critère est géométrique, pas photométrique : des pixels, par image.

        Une différence de pixels dépend du contenu — un dégradé lisse absorbe
        un mouvement qu'une photographie révèle. Le parcours, lui, ne dépend
        que de la caméra, et c'est donc lui qu'on contraint.
        """
        from pdz2.renderers.deterministic import MAX_CAMERA_TRAVEL

        largeur, images = 1080, 5.0 * 30  # un plan de cinq secondes à 30 i/s
        for energie in (0.35, 0.70):
            par_image = MAX_CAMERA_TRAVEL * energie * largeur / images
            assert par_image >= 0.5, (
                f"énergie {energie} : {par_image:.2f} pixel par image — sous le "
                "demi-pixel, un déplacement continu se confond avec du bruit"
            )

    def test_no_layer_is_nailed_to_the_frame(self) -> None:
        """Le fond suit la caméra, plus lentement. Il ne reste pas cloué.

        Un fond parfaitement immobile derrière un sujet qui glisse ne produit
        pas du relief : il produit l'impression d'une image fixe avec un
        élément qui dérive.
        """
        from pdz2.renderers.deterministic import PARALLAX_SPREAD

        for depth in (0.0, 0.25, 0.6, 0.9):
            facteur = (1.0 - PARALLAX_SPREAD) + PARALLAX_SPREAD * depth
            assert facteur > 0.4, f"profondeur {depth} : facteur {facteur:.2f}"

        proche = (1.0 - PARALLAX_SPREAD) + PARALLAX_SPREAD * 0.9
        loin = (1.0 - PARALLAX_SPREAD) + PARALLAX_SPREAD * 0.0
        assert proche > loin * 1.3, "sans écart entre les calques, plus de relief"

    def test_the_overscan_does_not_clip_the_travel_it_allows(self) -> None:
        """La marge plafonnait le parcours avant l'amplitude elle-même.

        Mesuré avant correction : un panoramique rendait exactement le même
        déplacement à énergie 0,5 et à énergie 1,0 — la marge saturait, et
        relever l'amplitude n'aurait rien changé au-delà de la moitié de
        l'échelle.
        """
        from pdz2.renderers.deterministic import _OVERSCAN, MAX_CAMERA_TRAVEL

        marge = _OVERSCAN - 1.0
        assert marge >= MAX_CAMERA_TRAVEL, (
            f"marge {marge:.2f} inférieure au parcours maximal "
            f"{MAX_CAMERA_TRAVEL:.2f} : le mouvement sature avant son amplitude"
        )


# ------------------------- le sujet doit bouger, ou son immobilité se déclarer


class TestLeMouvementDuSujet:
    """« Le moteur qui tourne, l'électricité qui bouge. »

    Recadrer une image fixe ou faire glisser des calques déplace la CAMÉRA.
    Rien ne bouge jamais dans le cadre. Le cahier des charges prévoit pourtant
    `MotionProgram.subject_motion` et le déclare source de vérité du mouvement.

    Le routeur enregistrait des dégradations pour la caméra, l'identité et le
    fournisseur — jamais pour le sujet. Un plan exigeant « rotation du sujet
    démontrant le mécanisme » recevait un panoramique, et le journal annonçait
    zéro dégradation. C'est la dégradation silencieuse que le §12 interdit.
    """

    def test_the_capability_table_tells_the_truth_about_the_strategies(self) -> None:
        """Aucune ligne annoncée sans code derrière — la règle du dépôt."""
        from pdz2.contracts.motion import MotionPrimitive
        from pdz2.contracts.render import RenderStrategy
        from pdz2.engines.routing.router import _SUBJECT_MOTION_BY_STRATEGY

        # Recadrer et faire glisser n'anime pas un sujet. La table doit le dire.
        assert _SUBJECT_MOTION_BY_STRATEGY[RenderStrategy.KEN_BURNS] == frozenset()
        assert _SUBJECT_MOTION_BY_STRATEGY[RenderStrategy.PARALLAX_2_5D] == frozenset()
        assert _SUBJECT_MOTION_BY_STRATEGY[RenderStrategy.STILL] == frozenset()

        # Le moteur procédural dessine, et sait faire tourner un calque.
        procedural = _SUBJECT_MOTION_BY_STRATEGY[RenderStrategy.PROCEDURAL]
        assert MotionPrimitive.ROTATE in procedural

    def test_a_subject_that_will_not_move_is_declared(self, tmp_path) -> None:
        from pdz2.engines.routing import RenderRouter
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        sortie = RenderRouter().route(
            episode_id="preuve",
            requested=episode.render_specs,
            motion_programs=episode.motion_programs,
            image_specs=episode.image_specs,
        )
        par_plan = {m.shot_id: m for m in episode.motion_programs}

        for executable in sortie.executables:
            programme = par_plan[executable.shot_id]
            demande = programme.subject_motion.primitive
            declare = [
                d for d in executable.degradations if d.field == "subject_motion"
            ]
            from pdz2.contracts.motion import MotionPrimitive
            from pdz2.engines.routing.router import _SUBJECT_MOTION_BY_STRATEGY

            tenable = demande in _SUBJECT_MOTION_BY_STRATEGY.get(
                executable.strategy, frozenset()
            )
            if demande is MotionPrimitive.STATIC or tenable:
                assert not declare, (
                    f"{executable.shot_id} : dégradation déclarée pour un "
                    "mouvement qui sera pourtant exécuté"
                )
            else:
                assert declare, (
                    f"{executable.shot_id} exige « {demande.value} » et reçoit "
                    f"{executable.strategy.value}, qui ne l'exécute pas — "
                    "aucune dégradation inscrite"
                )
                assert declare[0].requested == demande.value
                assert declare[0].executed == "static"

    def test_the_episode_no_longer_looks_flawless(self, tmp_path) -> None:
        """Un épisode aux huit plans immobiles ne doit pas se dire irréprochable."""
        from pdz2.engines.routing import RenderRouter
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        sortie = RenderRouter().route(
            episode_id="preuve",
            requested=episode.render_specs,
            motion_programs=episode.motion_programs,
            image_specs=episode.image_specs,
        )
        declarees = [
            d
            for e in sortie.executables
            for d in e.degradations
            if d.field == "subject_motion"
        ]
        assert declarees, (
            "aucun plan ne déclare que son sujet restera immobile, alors "
            "qu'aucune stratégie locale ne sait animer un sujet"
        )
