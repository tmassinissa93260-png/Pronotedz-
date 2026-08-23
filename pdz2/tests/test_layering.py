"""Tests d'architecture.

Ces tests ne vérifient pas un comportement mais une frontière. Ils échouent
le jour où quelqu'un mélange les trois couches, ou fait entrer un nom de
fournisseur dans le cœur du système.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from pdz2.contracts import DirectorState, RenderSpecExecutable, RenderSpecRequested, registry

PACKAGE_ROOT = Path(__file__).resolve().parents[1]

EXECUTION_ONLY_PACKAGES = {
    "pdz2.providers",
    "pdz2.renderers",
    "pdz2.engines",
    "pdz2.qa",
    "pdz2.repair",
    "pdz2.audio",
    "pdz2.editing",
    "pdz2.cli",
    "pdz2.storage",
    "pdz2.state",
}

# Marques et noms commerciaux qui n'ont rien à faire dans le cœur : ils
# n'apparaissent, plus tard, que dans les adaptateurs et la matrice de
# capacités mesurées.
PROVIDER_BRANDS = (
    "openai",
    "anthropic",
    "runway",
    "pika",
    "luma",
    "kling",
    "veo",
    "sora",
    "elevenlabs",
    "groq",
    "replicate",
    "fal.ai",
    "falai",
    "stability",
    "midjourney",
    "comfyui",
)


def _imports_of(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


def _python_files(package: str) -> list[Path]:
    directory = PACKAGE_ROOT / package
    return sorted(p for p in directory.rglob("*.py"))


class TestContractsStayIndependent:
    def test_contracts_import_nothing_from_the_execution_layers(self) -> None:
        offenders: list[str] = []
        for path in _python_files("contracts"):
            for module in _imports_of(path):
                for forbidden in EXECUTION_ONLY_PACKAGES:
                    if module == forbidden or module.startswith(f"{forbidden}."):
                        offenders.append(f"{path.name} importe {module}")
        assert not offenders, offenders

    def test_the_state_machine_only_knows_contracts(self) -> None:
        allowed_prefixes = ("pdz2.contracts", "pdz2.state")
        offenders: list[str] = []
        for path in _python_files("state"):
            for module in _imports_of(path):
                if module.startswith("pdz2.") and not module.startswith(allowed_prefixes):
                    offenders.append(f"{path.name} importe {module}")
        assert not offenders, offenders

    @pytest.mark.parametrize(
        "package", ["contracts", "state", "storage", "schemas", "engines"]
    )
    def test_no_provider_brand_in_the_core(self, package: str) -> None:
        offenders: list[str] = []
        for path in _python_files(package):
            lowered = path.read_text(encoding="utf-8").lower()
            for brand in PROVIDER_BRANDS:
                if brand in lowered:
                    offenders.append(f"{path.name} mentionne {brand!r}")
        assert not offenders, offenders


class TestLayerPurity:
    """NARRATIVE INTENT, RENDER SPECIFICATION et EXECUTION ne se mélangent pas."""

    RENDER_WORDS = {
        "provider",
        "model",
        "strategy",
        "fps",
        "resolution",
        "seed",
        "cost",
        "endpoint",
        "api",
    }

    def test_director_state_carries_no_render_field(self) -> None:
        leaked = [
            name
            for name in DirectorState.model_fields
            if any(word in name for word in self.RENDER_WORDS)
        ]
        assert not leaked, f"fuite d'exécution dans DirectorState : {leaked}"

    def test_shot_intent_carries_no_render_field(self) -> None:
        from pdz2.contracts import ShotIntent

        leaked = [
            name
            for name in ShotIntent.model_fields
            if any(word in name for word in self.RENDER_WORDS)
        ]
        assert not leaked, f"fuite d'exécution dans ShotIntent : {leaked}"

    def test_requested_spec_names_no_provider(self) -> None:
        fields = set(RenderSpecRequested.model_fields)
        assert "provider" not in fields
        assert "model" not in fields

    def test_executable_spec_is_the_only_side_that_names_a_provider(self) -> None:
        assert "provider" in RenderSpecExecutable.model_fields
        assert "model" in RenderSpecExecutable.model_fields

    def test_executable_spec_carries_no_narrative_field(self) -> None:
        narrative = {"thesis", "claim_id", "narrative_function", "audience", "tone"}
        leaked = narrative & set(RenderSpecExecutable.model_fields)
        assert not leaked, f"fuite narrative dans RenderSpecExecutable : {leaked}"


class TestNoArbitraryDictionaries:
    """Aucun dictionnaire libre ne remplace un contrat central."""

    def test_no_contract_exposes_a_raw_dict_field(self) -> None:
        offenders: list[str] = []
        for contract_type in registry.types():
            for name, field in contract_type.model_fields.items():
                annotation = str(field.annotation)
                if "dict[" in annotation.lower() or annotation.startswith("<class 'dict'"):
                    offenders.append(f"{contract_type.CONTRACT_NAME}.{name}: {annotation}")
        assert not offenders, offenders

    def test_every_contract_forbids_unknown_fields(self) -> None:
        offenders = [
            contract_type.CONTRACT_NAME
            for contract_type in registry.types()
            if contract_type.model_config.get("extra") != "forbid"
        ]
        assert not offenders, offenders


class TestAudioCoreStaysEngineAgnostic:
    """Un seul module de la chaîne audio a le droit de nommer un moteur.

    Le port, la mesure, l'assemblage et la timeline doivent survivre au
    remplacement du moteur de synthèse sans une ligne de changement.
    """

    ADAPTERS = {"espeak.py", "__init__.py"}
    """L'adaptateur nomme son moteur, et la façade du paquet le ré-exporte.

    Partout ailleurs — port, mesure, assemblage, timeline — le nom d'un moteur
    est une fuite d'exécution dans une couche qui doit l'ignorer."""

    def test_only_the_adapter_names_its_engine(self) -> None:
        offenders: list[str] = []
        for path in _python_files("audio"):
            if path.name in self.ADAPTERS:
                continue
            lowered = path.read_text(encoding="utf-8").lower()
            for brand in ("espeak", *PROVIDER_BRANDS):
                if brand in lowered:
                    offenders.append(f"{path.name} mentionne {brand!r}")
        assert not offenders, offenders

    def test_the_timeline_builder_knows_no_engine_at_all(self) -> None:
        from pdz2.audio import timeline

        source = Path(timeline.__file__).read_text(encoding="utf-8").lower()
        assert "espeak" not in source
        assert "subprocess" not in source


class TestPhaseHonesty:
    """Les paquets des phases suivantes restent vides, sans faux moteur."""

    UNIMPLEMENTED = ("providers", "renderers", "qa", "repair", "editing")
    """Paquets dont la phase n'est pas faite.

    `engines` en est sorti en phase 1, `audio` en phase 2."""

    @pytest.mark.parametrize("package", UNIMPLEMENTED)
    def test_unimplemented_packages_contain_only_their_notice(self, package: str) -> None:
        files = _python_files(package)
        assert [p.name for p in files] == ["__init__.py"], (
            f"{package} contient du code alors que sa phase n'est pas faite"
        )
        text = files[0].read_text(encoding="utf-8")
        assert "non implémenté" in text

    def test_the_engines_actually_shipped_are_the_ones_announced(self) -> None:
        """Un moteur annoncé dans `engines/__init__` doit exister, et inversement."""
        directory = PACKAGE_ROOT / "engines"
        present = sorted(
            path.name
            for path in directory.iterdir()
            if path.is_dir() and (path / "__init__.py").exists()
        )
        assert present == ["direction", "research", "script"]

    def test_no_reasoner_adapter_pretends_to_exist(self) -> None:
        """Le port `Reasoner` est défini, aucun adaptateur ne l'implémente.

        Le jour où un adaptateur arrive, ce test échoue — et c'est le moment
        de retirer la mention « aucun raisonneur branché » de `pdz2 phases`.
        """
        from pdz2.cli.main import IMPLEMENTED_PHASES

        adapters = _python_files("providers")
        assert [p.name for p in adapters] == ["__init__.py"]
        assert any("aucun raisonneur branché" in line for line in IMPLEMENTED_PHASES)


class TestIndependenceFromPdz1:
    """PDZ 2 ne doit rien à l'ancien système.

    L'ancien paquet `pdz/` vit dans le même dépôt. Ce test échoue au moindre
    emprunt : import, chemin en dur, ou lecture d'un de ses fichiers de
    configuration. « PDZ 1 peut exister à côté, PDZ 2 ne lui doit rien » est
    ainsi une propriété vérifiée, pas une intention.
    """

    FORBIDDEN_MODULE_PREFIXES = ("pdz.", "pdz2.tests.doubles_pdz1")
    FORBIDDEN_PATHS = ("pdz/", "modeles.yaml", "univers/", "donnees/")

    def test_no_module_of_pdz2_imports_the_old_package(self) -> None:
        offenders: list[str] = []
        for path in PACKAGE_ROOT.rglob("*.py"):
            for module in _imports_of(path):
                if module == "pdz" or module.startswith(self.FORBIDDEN_MODULE_PREFIXES):
                    offenders.append(f"{path.relative_to(PACKAGE_ROOT)} importe {module}")
        assert not offenders, offenders

    def test_no_module_of_pdz2_reaches_into_the_old_tree(self) -> None:
        offenders: list[str] = []
        for path in PACKAGE_ROOT.rglob("*.py"):
            if path == Path(__file__):  # ce fichier cite les motifs interdits
                continue
            text = path.read_text(encoding="utf-8")
            for needle in self.FORBIDDEN_PATHS:
                for quote in ('"', "'"):
                    if f"{quote}{needle}" in text or f"{quote}./{needle}" in text:
                        offenders.append(
                            f"{path.relative_to(PACKAGE_ROOT)} référence {needle!r}"
                        )
        assert not offenders, offenders

    def test_pdz2_is_importable_without_the_old_package(self) -> None:
        """Le paquet se charge même si `pdz` est introuvable."""
        import subprocess
        import sys

        script = (
            "import sys;"
            "sys.modules['pdz'] = None;"
            "import pdz2.contracts, pdz2.state, pdz2.storage, pdz2.cli;"
            "print('ok')"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=PACKAGE_ROOT.parent,
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout


class TestContractRegistryIsComplete:
    """Importer `pdz2.contracts` doit suffire à connaître tous les contrats.

    Un contrat déclaré ailleurs — dans un moteur, un adaptateur — resterait
    invisible du registre tant que ce module n'est pas importé : les schémas
    seraient incomplets, et la relecture d'un épisode échouerait sur un
    `contrat inconnu`. Ce test ferme cette porte.
    """

    def test_no_contract_is_declared_outside_the_contracts_package(self) -> None:
        offenders: list[str] = []
        for path in PACKAGE_ROOT.rglob("*.py"):
            if path.parts[-2] == "contracts" or "tests" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            if "@contract(" in text:
                offenders.append(str(path.relative_to(PACKAGE_ROOT)))
        assert not offenders, (
            f"contrats déclarés hors de `contracts/` : {offenders} — "
            "ils échapperaient au registre et aux schémas"
        )

    def test_importing_contracts_alone_registers_everything(self) -> None:
        import subprocess
        import sys

        script = (
            "import pdz2.contracts as c;"
            "print(len(c.registry.names()));"
            "import pdz2.engines.research, pdz2.engines.direction, pdz2.cli.main;"
            "print(len(c.registry.names()))"
        )
        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            cwd=PACKAGE_ROOT.parent,
        )
        assert result.returncode == 0, result.stderr
        before, after = result.stdout.split()
        assert before == after, (
            f"{int(after) - int(before)} contrat(s) apparaissent seulement "
            "après l'import d'un moteur"
        )
