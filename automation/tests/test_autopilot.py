"""Tests du moteur autopilot. Aucune dependance externe: python -m unittest."""

import json
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import autopilot  # noqa: E402
from autopilot import Config, ConfigError, Rule  # noqa: E402


def rule(name="r", match=None, action=None, enabled=True):
    return Rule(name=name, match=match or {}, action=action or {"type": "delete"},
                enabled=enabled)


class TempDirCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def touch(self, name, content="x", age_days=0.0):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        if age_days:
            stamp = time.time() - age_days * 86400
            import os
            os.utime(path, (stamp, stamp))
        return path

    def config(self, rules, **kwargs):
        kwargs.setdefault("source", self.root / "rules.json")
        return Config(watch_dir=self.root, rules=rules, **kwargs)


class TestMatching(TempDirCase):
    def test_regle_sans_critere_accepte_tout(self):
        self.assertTrue(autopilot.matches(rule(), self.touch("a.txt")))

    def test_extension_insensible_a_la_casse_et_au_point(self):
        r = rule(match={"ext": ["JPG", ".png"]})
        self.assertTrue(autopilot.matches(r, self.touch("photo.jpg")))
        self.assertTrue(autopilot.matches(r, self.touch("photo.PNG")))
        self.assertFalse(autopilot.matches(r, self.touch("note.txt")))

    def test_glob_et_name_contains(self):
        self.assertTrue(autopilot.matches(rule(match={"glob": "rapport-*.pdf"}),
                                          self.touch("rapport-2026.pdf")))
        self.assertFalse(autopilot.matches(rule(match={"glob": "rapport-*.pdf"}),
                                           self.touch("autre.pdf")))
        self.assertTrue(autopilot.matches(rule(match={"name_contains": "FACTURE"}),
                                          self.touch("ma-facture.pdf")))

    def test_exclude_glob_ecarte(self):
        r = rule(match={"ext": ["pdf"], "exclude_glob": "20*-*"})
        self.assertTrue(autopilot.matches(r, self.touch("facture.pdf")))
        self.assertFalse(autopilot.matches(r, self.touch("2026-08-27-facture.pdf")))

    def test_taille_min_et_max(self):
        petit = self.touch("petit.bin", "a" * 100)
        gros = self.touch("gros.bin", "a" * 5000)
        self.assertFalse(autopilot.matches(rule(match={"min_size_kb": 1}), petit))
        self.assertTrue(autopilot.matches(rule(match={"min_size_kb": 1}), gros))
        self.assertTrue(autopilot.matches(rule(match={"max_size_kb": 1}), petit))

    def test_age_minimum(self):
        vieux = self.touch("vieux.tmp", age_days=10)
        neuf = self.touch("neuf.tmp")
        r = rule(match={"older_than_days": 7})
        self.assertTrue(autopilot.matches(r, vieux))
        self.assertFalse(autopilot.matches(r, neuf))

    def test_tous_les_criteres_doivent_passer(self):
        r = rule(match={"ext": ["pdf"], "name_contains": "facture"})
        self.assertFalse(autopilot.matches(r, self.touch("facture.txt")))
        self.assertFalse(autopilot.matches(r, self.touch("devis.pdf")))
        self.assertTrue(autopilot.matches(r, self.touch("facture.pdf")))

    def test_premiere_regle_gagne_et_desactivee_ignoree(self):
        a = rule(name="a", match={"ext": ["pdf"]}, enabled=False)
        b = rule(name="b", match={"ext": ["pdf"]})
        c = rule(name="c", match={"ext": ["pdf"]})
        found = autopilot.first_match([a, b, c], self.touch("x.pdf"))
        self.assertEqual(found.name, "b")


class TestActions(TempDirCase):
    def test_move_cree_le_dossier_cible(self):
        src = self.touch("photo.jpg")
        dest = self.root / "out"
        r = rule(action={"type": "move", "dest": str(dest)})
        entry = autopilot.apply_action(r, src, self.config([r]), dry_run=False)
        self.assertEqual(entry["status"], "ok")
        self.assertFalse(src.exists())
        self.assertTrue((dest / "photo.jpg").exists())

    def test_dry_run_ne_touche_a_rien(self):
        src = self.touch("photo.jpg")
        r = rule(action={"type": "move", "dest": str(self.root / "out")})
        entry = autopilot.apply_action(r, src, self.config([r]), dry_run=True)
        self.assertTrue(entry["dry_run"])
        self.assertTrue(src.exists())
        self.assertFalse((self.root / "out").exists())

    def test_jamais_d_ecrasement(self):
        dest = self.root / "out"
        dest.mkdir()
        (dest / "photo.jpg").write_text("deja la", encoding="utf-8")
        src = self.touch("photo.jpg", "nouveau")
        r = rule(action={"type": "move", "dest": str(dest)})
        entry = autopilot.apply_action(r, src, self.config([r]), dry_run=False)
        self.assertEqual(Path(entry["target"]).name, "photo-1.jpg")
        self.assertEqual((dest / "photo.jpg").read_text(encoding="utf-8"), "deja la")
        self.assertEqual((dest / "photo-1.jpg").read_text(encoding="utf-8"), "nouveau")

    def test_copy_conserve_la_source(self):
        src = self.touch("doc.pdf")
        r = rule(action={"type": "copy", "dest": str(self.root / "backup")})
        autopilot.apply_action(r, src, self.config([r]), dry_run=False)
        self.assertTrue(src.exists())
        self.assertTrue((self.root / "backup" / "doc.pdf").exists())

    def test_rename_avec_gabarit(self):
        src = self.touch("facture.pdf")
        r = rule(action={"type": "rename", "template": "{date}-{stem}.{ext}"})
        entry = autopilot.apply_action(r, src, self.config([r]), dry_run=False)
        self.assertRegex(Path(entry["target"]).name, r"^\d{4}-\d{2}-\d{2}-facture\.pdf$")
        self.assertFalse(src.exists())

    def test_rename_ne_touche_pas_un_nom_deja_conforme(self):
        src = self.touch("deja-bon.txt")
        r = rule(action={"type": "rename", "template": "{name}"})
        entry = autopilot.apply_action(r, src, self.config([r]), dry_run=False)
        self.assertEqual(entry["status"], "skip")
        self.assertTrue(src.exists())
        self.assertFalse((self.root / "deja-bon-1.txt").exists())

    def test_rename_est_idempotent_sur_plusieurs_passes(self):
        # Le piege du mode watch: la regle doit ecarter ses propres sorties.
        self.touch("facture.pdf")
        rules = [rule(match={"ext": ["pdf"], "exclude_glob": "[0-9][0-9][0-9][0-9]-*"},
                      action={"type": "rename", "template": "{date}-{stem}.{ext}"})]
        config = self.config(rules)
        autopilot.run_once(config, dry_run=False)
        noms_apres_1 = sorted(p.name for p in self.root.iterdir())
        autopilot.run_once(config, dry_run=False)
        autopilot.run_once(config, dry_run=False)
        self.assertEqual(sorted(p.name for p in self.root.iterdir()), noms_apres_1)
        self.assertEqual(len(noms_apres_1), 1)

    def test_rename_refuse_un_separateur(self):
        src = self.touch("a.txt")
        r = rule(action={"type": "rename", "template": "sous/dossier/{name}"})
        entry = autopilot.apply_action(r, src, self.config([r]), dry_run=False)
        self.assertEqual(entry["status"], "error")
        self.assertTrue(src.exists())

    def test_delete(self):
        src = self.touch("jetable.tmp")
        r = rule(action={"type": "delete"})
        autopilot.apply_action(r, src, self.config([r]), dry_run=False)
        self.assertFalse(src.exists())

    def test_run_capture_le_code_retour(self):
        src = self.touch("a.txt")
        r = rule(action={"type": "run", "command": [sys.executable, "-c",
                                                    "import sys; print(sys.argv[1])", "{path}"]})
        entry = autopilot.apply_action(r, src, self.config([r]), dry_run=False)
        self.assertEqual(entry["returncode"], 0)
        self.assertEqual(entry["command"][-1], str(src))

    def test_run_en_echec_est_signale_sans_lever(self):
        src = self.touch("a.txt")
        r = rule(action={"type": "run", "command": [sys.executable, "-c", "raise SystemExit(3)"]})
        entry = autopilot.apply_action(r, src, self.config([r]), dry_run=False)
        self.assertEqual(entry["status"], "error")
        self.assertEqual(entry["returncode"], 3)


class TestEngine(TempDirCase):
    def test_run_once_trie_par_regle(self):
        self.touch("photo.jpg")
        self.touch("note.txt")
        self.touch("archive.zip")
        rules = [
            rule(name="images", match={"ext": ["jpg"]},
                 action={"type": "move", "dest": str(self.root / "img")}),
            rule(name="zips", match={"ext": ["zip"]},
                 action={"type": "move", "dest": str(self.root / "zip")}),
        ]
        entries = autopilot.run_once(self.config(rules), dry_run=False)
        self.assertEqual(len(entries), 2)
        self.assertTrue((self.root / "img" / "photo.jpg").exists())
        self.assertTrue((self.root / "zip" / "archive.zip").exists())
        self.assertTrue((self.root / "note.txt").exists())  # aucune regle: intact

    def test_fichiers_caches_ignores_par_defaut(self):
        self.touch(".secret.jpg")
        rules = [rule(match={"ext": ["jpg"]}, action={"type": "delete"})]
        self.assertEqual(autopilot.run_once(self.config(rules)), [])
        self.assertTrue((self.root / ".secret.jpg").exists())

    def test_non_recursif_par_defaut(self):
        self.touch("sous/photo.jpg")
        rules = [rule(match={"ext": ["jpg"]}, action={"type": "delete"})]
        self.assertEqual(autopilot.run_once(self.config(rules)), [])
        entries = autopilot.run_once(self.config(rules, recursive=True))
        self.assertEqual(len(entries), 1)

    def test_settle_seconds_ignore_les_fichiers_frais(self):
        self.touch("frais.jpg")
        rules = [rule(match={"ext": ["jpg"]}, action={"type": "delete"})]
        self.assertEqual(autopilot.run_once(self.config(rules, settle_seconds=60)), [])

    def test_journal_ecrit_en_jsonl(self):
        self.touch("a.tmp")
        log = self.root / "journal.jsonl"
        rules = [rule(match={"ext": ["tmp"]}, action={"type": "delete"})]
        autopilot.run_once(self.config(rules, log_file=log), dry_run=False)
        lines = log.read_text(encoding="utf-8").strip().splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(json.loads(lines[0])["action"], "delete")

    def test_dry_run_n_ecrit_pas_le_journal(self):
        self.touch("a.tmp")
        log = self.root / "journal.jsonl"
        rules = [rule(match={"ext": ["tmp"]}, action={"type": "delete"})]
        autopilot.run_once(self.config(rules, log_file=log), dry_run=True)
        self.assertFalse(log.exists())

    def test_une_regle_en_echec_n_arrete_pas_la_passe(self):
        self.touch("a.txt")
        self.touch("b.jpg")
        rules = [
            rule(name="casse", match={"ext": ["txt"]},
                 action={"type": "rename", "template": "x/{name}"}),
            rule(name="ok", match={"ext": ["jpg"]},
                 action={"type": "move", "dest": str(self.root / "img")}),
        ]
        entries = autopilot.run_once(self.config(rules), dry_run=False)
        self.assertEqual([e["status"] for e in entries], ["error", "ok"])
        self.assertTrue((self.root / "img" / "b.jpg").exists())

    def test_dossier_surveille_absent(self):
        config = Config(watch_dir=self.root / "nexiste-pas", rules=[rule()])
        self.assertEqual(autopilot.run_once(config), [])


class TestConfig(TempDirCase):
    def write(self, payload):
        path = self.root / "rules.json"
        path.write_text(json.dumps(payload) if not isinstance(payload, str) else payload,
                        encoding="utf-8")
        return path

    def test_chemins_relatifs_resolus_depuis_le_fichier(self):
        path = self.write({
            "watch_dir": "inbox",
            "log_file": "logs/journal.jsonl",
            "rules": [{"name": "r", "action": {"type": "delete"}}],
        })
        config = autopilot.load_config(path)
        self.assertEqual(config.watch_dir, self.root / "inbox")
        self.assertEqual(config.log_file, self.root / "logs" / "journal.jsonl")

    def test_erreurs_de_config(self):
        cases = [
            ({"rules": [{"action": {"type": "delete"}}]}, "watch_dir"),
            ({"watch_dir": ".", "rules": []}, "aucune regle"),
            ({"watch_dir": ".", "rules": [{"name": "r", "action": {"type": "boum"}}]}, "inconnue"),
            ({"watch_dir": ".", "rules": [{"name": "r", "action": {"type": "move"}}]}, "dest"),
            ({"watch_dir": ".", "rules": [{"name": "r", "action": {"type": "rename"}}]}, "template"),
            ({"watch_dir": ".", "rules": [{"name": "r", "action": {"type": "run"}}]}, "command"),
            ({"watch_dir": ".", "rules": [{"name": "r"}]}, "action"),
        ]
        for payload, needle in cases:
            with self.subTest(needle=needle):
                with self.assertRaises(ConfigError) as ctx:
                    autopilot.load_config(self.write(payload))
                self.assertIn(needle, str(ctx.exception))

    def test_json_invalide_et_fichier_absent(self):
        with self.assertRaises(ConfigError):
            autopilot.load_config(self.write("{pas du json"))
        with self.assertRaises(ConfigError):
            autopilot.load_config(self.root / "absent.json")

    def test_config_d_exemple_est_valide(self):
        path = self.write(autopilot.EXAMPLE_CONFIG)
        config = autopilot.load_config(path)
        self.assertEqual(len(config.rules), len(autopilot.EXAMPLE_CONFIG["rules"]))


class TestCli(TempDirCase):
    def test_init_puis_run_dry_run(self):
        path = self.root / "rules.json"
        self.assertEqual(autopilot.main(["init", "--config", str(path)]), 0)
        self.assertTrue(path.exists())
        self.assertEqual(autopilot.main(["init", "--config", str(path)]), 1)  # refuse d'ecraser
        self.assertEqual(autopilot.main(["init", "--config", str(path), "--force"]), 0)

    def test_run_sur_config_invalide_retourne_2(self):
        path = self.root / "rules.json"
        path.write_text("{}", encoding="utf-8")
        self.assertEqual(autopilot.main(["run", "--config", str(path)]), 2)

    def test_run_complet(self):
        inbox = self.root / "inbox"
        inbox.mkdir()
        (inbox / "photo.jpg").write_text("x", encoding="utf-8")
        path = self.root / "rules.json"
        path.write_text(json.dumps({
            "watch_dir": "inbox",
            "rules": [{"name": "img", "match": {"ext": ["jpg"]},
                       "action": {"type": "move", "dest": "tri"}}],
        }), encoding="utf-8")
        self.assertEqual(autopilot.main(["run", "--config", str(path), "--dry-run"]), 0)
        self.assertTrue((inbox / "photo.jpg").exists())
        self.assertEqual(autopilot.main(["run", "--config", str(path)]), 0)
        self.assertTrue((self.root / "tri" / "photo.jpg").exists())


if __name__ == "__main__":
    unittest.main()
