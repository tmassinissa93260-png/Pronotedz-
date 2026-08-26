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

        # Le sujet de l'épisode passe devant depuis le run #8 : sans lui, la
        # phrase ne nomme aucun domaine et le fournisseur complète avec le
        # décor de la bible. La preuve vient immédiatement après, et toujours
        # avant l'esthétique.
        assert prompt.startswith("Sujet de la séquence")
        position_preuve = prompt.index("L'image doit rendre visible")
        assert position_preuve < prompt.index("Style :")
        assert spec.evidence_required.rstrip(".") in prompt
        assert spec.subject_matter and spec.subject_matter in prompt



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

    def test_a_subject_that_must_move_is_routed_where_it_can(self, tmp_path) -> None:
        """Ce test affirmait l'inverse, et il avait raison de le faire.

        Il vérifiait qu'un épisode aux plans immobiles cessait de se présenter
        comme irréprochable — à une époque où AUCUNE stratégie locale ne savait
        animer un sujet. La grammaire de mouvement dessinée a changé ce fait :
        le procédural exécute désormais les neuf primitives animables.

        L'invariant utile n'est donc plus « la lacune est déclarée » mais « le
        mouvement demandé est exécuté, ou déclaré ». Le premier cas est
        vérifié ici, le second par le test précédent.
        """
        from pdz2.contracts.motion import MotionPrimitive
        from pdz2.engines.routing import RenderRouter
        from pdz2.engines.routing.router import _SUBJECT_MOTION_BY_STRATEGY
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        sortie = RenderRouter().route(
            episode_id="preuve",
            requested=episode.render_specs,
            motion_programs=episode.motion_programs,
            image_specs=episode.image_specs,
        )
        par_plan = {m.shot_id: m for m in episode.motion_programs}

        mobiles = 0
        for executable in sortie.executables:
            demande = par_plan[executable.shot_id].subject_motion.primitive
            if demande is MotionPrimitive.STATIC:
                continue
            mobiles += 1
            tenable = demande in _SUBJECT_MOTION_BY_STRATEGY.get(
                executable.strategy, frozenset()
            )
            declare = any(
                d.field == "subject_motion" for d in executable.degradations
            )
            assert tenable or declare, (
                f"{executable.shot_id} exige « {demande.value} », reçoit "
                f"{executable.strategy.value} qui ne l'exécute pas, et ne le "
                "déclare pas"
            )

        assert mobiles, "l'épisode de référence ne demande aucun mouvement de sujet"

    def test_the_upgrade_is_visible_in_the_routing_notes(self, tmp_path) -> None:
        """Un choix qu'on ne lit nulle part est un choix qu'on ne peut pas discuter.

        Relever la visée n'est pas une dégradation — le plan reçoit plus que
        ce que l'énergie seule lui donnait — donc rien ne l'inscrivait.
        """
        from pdz2.engines.routing import RenderRouter
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        sortie = RenderRouter().route(
            episode_id="preuve",
            requested=episode.render_specs,
            motion_programs=episode.motion_programs,
            image_specs=episode.image_specs,
        )
        releves = [n for n in sortie.notes if "le sujet doit exécuter" in n]
        assert releves, "aucun relèvement de visée n'apparaît dans les notes"
        assert any("procedural" in n for n in releves)


# ---------------------------------------------- ce que le run #8 a mis à nu


class TestLeSujetDeLEpisodeAtteintLeFournisseur:
    """La commande doit nommer le domaine, sinon le décor le remplace.

    Le run #8 a produit huit plans sur « Comment fonctionne une voiture
    électrique ? ». Le prompt intégral d'un plan large, relu par
    `pdz2 prompts`, disait ceci — et rien de plus :

        Ouverture dans le registre décidé : technical. Cadrage : wide, angle
        low, sujet center. Style : technical — clean high-tech. Lumière :
        lumière froide, néons bleus. […] Décor : atelier de fabrication et
        laboratoire. Palette : #1A73E8, #FFFFFF, #000000.

    Ni voiture, ni moteur, ni batterie. Le seul substantif concret de la
    phrase était le décor décidé par la bible, et le fournisseur l'a rendu :
    un entrepôt de cartons, un garage vide, un couloir de centre commercial,
    un homme de dos dans une embrasure. Quatre plans sur huit sans rapport
    avec le sujet.
    """

    def test_the_image_contract_carries_the_topic(self, tmp_path) -> None:
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        for spec in episode.image_specs:
            assert spec.subject_matter, f"{spec.shot_id} ne sait pas de quoi on parle"

    def test_every_layer_prompt_names_the_topic(self, tmp_path) -> None:
        """Un appel par calque : aucun ne doit partir sans le domaine."""
        from pdz2.providers.prompting import image_prompt
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        for spec in episode.image_specs:
            for calque in spec.layers:
                prompt = image_prompt(spec, episode.bible, calque)
                assert spec.subject_matter in prompt, (
                    f"{spec.shot_id}/{calque.role.value} : commande sans domaine"
                )

    def test_framing_shots_no_longer_ask_for_a_register_name(self, tmp_path) -> None:
        """« Ouverture dans le registre décidé : technical » n'est pas une image."""
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        for shot in episode.graph.shots:
            assert "registre décidé" not in shot.visual_subject, (
                f"{shot.shot_id} commande une étiquette de style, pas une scène"
            )


class TestLeProceduralNeSAppliquePasPartout:
    """Le relèvement vers le procédural doit répondre à un mécanisme réel.

    Les huit plans du run #8 ont été routés en `procedural`. La cause est dans
    `subject_motion_for` : elle rend `LINEAR` — « déplacement du sujet dans le
    cadre » — pour tout plan dont l'énergie dépasse le seuil de verrouillage
    et qui ne porte pas d'affirmation de mécanisme, c'est-à-dire presque tous.
    `_aim_for_subject` voyait une primitive animable et relevait.

    À l'écran : des pointes de flux estampillées sur un entrepôt de cartons et
    sur un homme de dos. Une dérive du sujet n'est pas un mécanisme ; il n'y a
    rien de vrai à en dessiner.
    """

    def test_a_plain_drift_does_not_reach_the_procedural(self) -> None:
        from pdz2.contracts.motion import MotionPrimitive
        from pdz2.contracts.render import RenderStrategy
        from pdz2.engines.routing.router import _MECHANICAL, RenderRouter

        for primitive in (MotionPrimitive.LINEAR, MotionPrimitive.SCALE,
                          MotionPrimitive.JITTER, MotionPrimitive.STATIC):
            assert primitive not in _MECHANICAL
        programme = _programme(MotionPrimitive.LINEAR)
        for visee in (RenderStrategy.KEN_BURNS, RenderStrategy.PARALLAX_2_5D):
            assert RenderRouter._aim_for_subject(visee, programme) is visee

    def test_a_mechanism_still_reaches_the_procedural(self) -> None:
        from pdz2.contracts.motion import MotionPrimitive
        from pdz2.contracts.render import RenderStrategy
        from pdz2.engines.routing.router import RenderRouter

        for primitive in (MotionPrimitive.ROTATE, MotionPrimitive.FLOW,
                          MotionPrimitive.OSCILLATE):
            releve = RenderRouter._aim_for_subject(
                RenderStrategy.KEN_BURNS, _programme(primitive)
            )
            assert releve is RenderStrategy.PROCEDURAL, primitive

    def test_a_consequence_claim_now_asks_for_a_flow(self) -> None:
        """« Électricité qui bouge » n'avait aucun chemin : tout tombait en LINEAR."""
        from pdz2.contracts.motion import MotionPrimitive
        from pdz2.contracts.research import ClaimKind
        from pdz2.engines.shots.grammar import subject_motion_for

        flux = subject_motion_for(motion_target=0.6, claim_kind=ClaimKind.CONSEQUENCE)
        assert flux.primitive is MotionPrimitive.FLOW
        rotation = subject_motion_for(motion_target=0.6, claim_kind=ClaimKind.MECHANISM)
        assert rotation.primitive is MotionPrimitive.ROTATE
        reste = subject_motion_for(motion_target=0.6, claim_kind=ClaimKind.FACT)
        assert reste.primitive is MotionPrimitive.LINEAR


class TestLesIndicateursSeVoient:
    """Ils étaient peints en noir opaque sur des photographies sombres.

    `_teintes` prenait `palette[2]` pour l'accent et `palette[3]` pour le
    rappel, en supposant une palette ordonnée dominante d'abord. Le
    raisonneur du run #8 a rendu `#1A73E8, #FFFFFF, #000000` : les deux
    indices tombaient sur le noir. Les vingt-et-une pointes du plan large se
    lisaient comme de la poussière sur l'objectif.
    """

    PALETTE_DU_RUN_8 = [(0x1A, 0x73, 0xE8), (255, 255, 255), (0, 0, 0)]

    def test_the_accent_is_chosen_against_the_measured_background(self) -> None:
        from pdz2.renderers.mechanism import _luminance, _teintes

        for fond in (0.05, 0.37, 0.5, 0.95):
            accent, rappel = _teintes(self.PALETTE_DU_RUN_8, fond)
            for couleur in (accent, rappel):
                assert abs(_luminance(couleur) - fond) >= 0.25, (
                    f"fond {fond} : {couleur} ne se détache pas"
                )

    def test_both_tones_sit_on_the_same_side_of_the_background(self) -> None:
        """Un liseré unique ne peut pas cerner un trait clair et un trait sombre."""
        from pdz2.renderers.mechanism import _luminance, _teintes

        for fond in (0.1, 0.37, 0.6, 0.9):
            accent, rappel = _teintes(self.PALETTE_DU_RUN_8, fond)
            assert (_luminance(accent) > fond) is (_luminance(rappel) > fond)

    def test_an_unusable_palette_falls_back_rather_than_hiding(self) -> None:
        from pdz2.renderers.mechanism import _luminance, _teintes

        gris = [(120, 120, 120), (130, 130, 130)]
        accent, _ = _teintes(gris, 0.5)
        assert abs(_luminance(accent) - 0.5) >= 0.25

    def test_the_indicators_actually_change_the_pixels(self) -> None:
        """Sur une photographie réelle, et pas seulement sur un aplat."""
        from PIL import Image

        from pdz2.contracts.motion import MotionPrimitive
        from pdz2.renderers.mechanism import draw_mechanism

        fond = Image.new("RGB", (216, 384), (60, 62, 70))
        rendu = draw_mechanism(
            fond, _programme(MotionPrimitive.ROTATE), 0.35,
            palette=self.PALETTE_DU_RUN_8,
        )
        differents = sum(
            1 for a, b in zip(fond.tobytes(), rendu.tobytes(), strict=True) if a != b
        )
        assert differents > 0, "aucun pixel n'a bougé"


class TestLaRotationNOuvrePlusDeCoinsNoirs:
    """Faire tourner le calque entier n'est pas faire tourner le sujet.

    `_spin` appliquait `Image.rotate` au calque du sujet, jusqu'à
    `120° × énergie`. Sur un cadrage plat, `layers_for` ne rend qu'un calque :
    il n'y a rien sous les coins découverts, et le vide est le noir de la
    toile. Mesuré sur le run #8 — S03 33 % de pixels quasi noirs en moyenne,
    jusqu'à 40 % ; S04 16 % ; S05 11 %. Les trois plans à cadrage plat, et eux
    seuls.
    """

    def test_the_subject_layer_is_returned_untouched(self) -> None:
        from PIL import Image

        from pdz2.contracts.motion import MotionPrimitive
        from pdz2.renderers.deterministic import DeterministicRenderer

        calque = Image.new("RGBA", (64, 128), (200, 60, 40, 255))
        rendu = DeterministicRenderer._spin(
            calque, _programme(MotionPrimitive.ROTATE), 1.0
        )
        assert rendu.tobytes() == calque.tobytes(), (
            "le calque a été transformé : les coins redeviendront noirs"
        )


def _programme(primitive):
    """Un `MotionProgram` minimal portant le mouvement de sujet demandé."""
    from pdz2.contracts.common import Vec3
    from pdz2.contracts.motion import (
        MotionDescriptor,
        MotionPrimitive,
        MotionProgram,
        PerceptualTarget,
        Trajectory,
    )

    # Chaque primitive a ses paramètres obligatoires : le contrat les exige,
    # et un helper de test qui les contournerait ne testerait pas grand-chose.
    parametres: dict = {"primitive": primitive, "amplitude": 90.0, "axis": Vec3(y=1.0)}
    if primitive in {MotionPrimitive.LINEAR, MotionPrimitive.FLOW}:
        parametres["control_points"] = [Vec3(), Vec3(x=0.6)]
    elif primitive in {MotionPrimitive.ARC, MotionPrimitive.SPIRAL}:
        parametres["control_points"] = [Vec3(), Vec3(x=0.3), Vec3(x=0.6)]
    elif primitive in {MotionPrimitive.OSCILLATE, MotionPrimitive.JITTER}:
        parametres["frequency_hz"] = 1.5
    if primitive is MotionPrimitive.STATIC:
        parametres = {}
    trajectoire = Trajectory(**parametres)
    return MotionProgram(
        shot_id="S00",
        camera_program_id="cam",
        intensity=0.6,
        subject_motion=MotionDescriptor(
            primitive=primitive,
            direction=Vec3(x=1.0),
            magnitude=0.6,
            trajectory=trajectoire,
        )
        if primitive is not MotionPrimitive.STATIC
        else MotionDescriptor(),
        trajectory=trajectoire,
        perceptual_target=PerceptualTarget(
            motion_energy=0.5, visual_novelty=0.5, readability=0.6
        ),
    )


class TestEmpilerDesImagesOpaquesNEstPasComposer:
    """Le défaut le plus coûteux des runs #7 et #8, par ses deux bouts.

    `flux`, chez fal, rend un PNG **opaque** : alpha = 255 partout. Empiler
    quatre images opaques ne compose rien — chacune remplace la précédente, et
    le composite est exactement la dernière peinte.

    * Run #7, tri descendant : la dernière peinte était la plus **lointaine**.
      Le composite valait la génération demandée pour « fond lointain ».
    * Run #8, tri corrigé en croissant : la dernière peinte est la plus
      **proche**. Le composite vaut la génération demandée pour « éléments de
      premier plan de la scène, cadre partiel » — la moins susceptible de
      montrer le sujet. Des cartons au premier plan d'un entrepôt, un anneau
      de néon dans un couloir, un homme de dos dans une embrasure.

    Trois images sur quatre payées et jetées, à chaque plan large.

    Le tri n'était pas le problème. Le problème est qu'on demandait des
    calques à un moteur qui n'en sait pas rendre.
    """

    def test_the_remote_engine_says_it_cannot_separate_layers(self) -> None:
        from pdz2.providers.fal import FalImageProvider

        assert FalImageProvider().supports_alpha_layers is False

    def test_the_local_engine_says_it_can(self) -> None:
        from pdz2.engines.imagery.renderer import ProceduralImageRenderer

        assert ProceduralImageRenderer.supports_alpha_layers is True

    def test_a_non_separable_engine_is_asked_for_one_layer(self) -> None:
        """Et ce calque porte la scène entière, pas un avant-plan partiel."""
        from pdz2.contracts.enums import Framing
        from pdz2.contracts.visual import LayerRole

        for framing in (Framing.WIDE, Framing.MEDIUM, Framing.CUTAWAY_DIAGRAM):
            calques = layers_for(framing, "un rotor dans son stator", separable=False)
            assert len(calques) == 1, f"{framing.value} : {len(calques)} calques"
            assert calques[0].role is LayerRole.SUBJECT
            assert calques[0].must_be_separable is False
            assert "sujet exclu" not in calques[0].description
            assert "cadre partiel" not in calques[0].description

    def test_a_separable_engine_keeps_its_depth(self) -> None:
        from pdz2.contracts.enums import Framing

        assert len(layers_for(Framing.WIDE, "x", separable=True)) == 4

    def test_the_compiler_follows_the_engine(self, tmp_path) -> None:
        from pdz2.contracts.direction import DirectorState
        from pdz2.contracts.research import TopicRequest
        from pdz2.contracts.shots import ShotGraph
        from pdz2.contracts.visual import VisualBible
        from pdz2.engines.imagery import ImageSpecCompiler
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        commun: dict = {
            "shot_graph": episode.graph,
            "visual_bible": episode.bible,
            "director_state": episode.director_state,
            "request": episode.request,
        }
        assert isinstance(commun["shot_graph"], ShotGraph)
        assert isinstance(commun["visual_bible"], VisualBible)
        assert isinstance(commun["director_state"], DirectorState)
        assert isinstance(commun["request"], TopicRequest)

        opaque = ImageSpecCompiler(separable_layers=False).compile(**commun)
        assert all(len(spec.layers) == 1 for spec in opaque.specs)
        assert any("calques non séparables" in note for note in opaque.notes)

        alpha = ImageSpecCompiler(separable_layers=True).compile(**commun)
        assert max(len(spec.layers) for spec in alpha.specs) > 1

    def test_stacking_opaque_layers_keeps_only_the_last(self) -> None:
        """La mesure qui établit le défaut, pour qu'il ne revienne pas.

        Ce n'est pas un test de régression sur `_composer` : c'est la preuve
        que l'empilement d'images opaques ne peut pas fonctionner, quelle que
        soit la direction du tri. La conclusion est qu'on ne doit pas
        l'employer, pas qu'on doit le trier autrement.
        """
        from PIL import Image

        fond = Image.new("RGB", (4, 4), (0, 0, 0))
        couleurs = [(10, 20, 30), (70, 20, 30), (130, 20, 30), (190, 20, 30)]
        for couleur in couleurs:
            dessus = Image.new("RGB", (4, 4), couleur).convert("RGBA")
            assert min(dessus.split()[3].tobytes()) == 255, "alpha non opaque"
            fond.paste(dessus, (0, 0), dessus)
        assert fond.getpixel((0, 0)) == couleurs[-1]


class TestLaCommandeEstDominéeParSonSujet:
    """7,3 % du run #8 nommaient le sujet. 54 % décrivaient le style.

    Sur les 904 caractères réellement envoyés, 66 nommaient le sujet et 488
    récitaient la bible — un rapport de sept contre un. Le seul substantif
    concret qui pesait était le décor décidé par la bible : « atelier de
    fabrication et laboratoire ». Le fournisseur a rendu des ateliers, et il
    avait raison de le faire.
    """

    def test_what_must_be_visible_weighs_at_least_as_much_as_style(
        self, tmp_path
    ) -> None:
        from pdz2.providers.prompting import image_prompt
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        for spec in episode.image_specs:
            for calque in spec.layers:
                prompt = image_prompt(spec, episode.bible, calque)
                coupure = prompt.find("Cadrage :")
                assert coupure > 0, "la partie esthétique a disparu entièrement"
                assert coupure >= len(prompt) - coupure, (
                    f"{spec.shot_id}/{calque.role.value} : le style pèse "
                    f"{len(prompt) - coupure} car. contre {coupure} au sujet"
                )

    def test_the_decor_comes_last_since_it_is_what_misled_the_engine(
        self, tmp_path
    ) -> None:
        """Il reste transmis — il passe simplement après tout le reste."""
        from pdz2.providers.prompting import _style
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        style = _style(episode.image_specs[0], episode.bible)
        assert episode.bible.environment in style
        assert style.index(episode.bible.environment) > style.index(
            episode.bible.style
        )

    def test_the_style_is_cut_rather_than_the_subject(self) -> None:
        from pdz2.providers.prompting import _tenir_le_budget

        quoi = ["a" * 100]
        garde = _tenir_le_budget(quoi, ["b" * 300])
        assert garde and len(garde[0]) <= 100
        assert garde[0].endswith("…"), "une coupe muette est une coupe cachée"

    def test_invented_text_is_refused(self, tmp_path) -> None:
        """Le run #8 a rendu « MITSUBAMOX 197 » et « 66 kWh / 360am / BP-001 ».

        Le prompt négatif y était vide : ni la bible ni la spécification ne
        remplissaient `forbidden`. Un texte inventé sur une image pédagogique
        se lit comme une donnée, et il est faux.
        """
        from pdz2.providers.prompting import negative_prompt
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        for spec in episode.image_specs:
            interdits = negative_prompt(spec, episode.bible)
            assert interdits.strip(), f"{spec.shot_id} : aucun interdit transmis"
            for terme in ("texte", "filigrane", "logo"):
                assert terme in interdits

    def test_the_decided_forbiddens_still_come_first(self, tmp_path) -> None:
        """Le plancher technique ne prend la place d'aucune décision."""
        from pdz2.providers.prompting import _ARTEFACTS, negative_prompt
        from pdz2.tests import pipeline

        episode = pipeline.build_episode(tmp_path, through_render_spec=True)
        spec = episode.image_specs[0].model_copy(update={"forbidden": ["une chose"]})
        interdits = negative_prompt(spec, episode.bible)
        assert interdits.startswith("une chose")
        assert interdits.index("une chose") < interdits.index(_ARTEFACTS[0])
