# 02 — Les agents

## C'est quoi un « agent » ici

Un agent = **un petit spécialiste qui fait une seule chose**.
Il reçoit quelque chose, il rend quelque chose. C'est tout.

On passe de 18 agents (version SaaS) à **12**. J'ai supprimé ceux qui n'existaient que
pour gérer des clients : surveillance des budgets par compte, publication multi-comptes,
modération, statistiques de plateforme.

## Ce que chaque agent déclare

Un fichier de config par agent. Pas de code compliqué :

```yaml
id: script
description: "Écrit le script scène par scène"

modele: claude-sonnet-4-5        # ou juste "tier.qualite"
repli: claude-haiku-4-5          # si le premier plante
cout_max: 0.10                   # € — au-delà, il s'arrête

prompt: creative/script@3.0.0    # le prompt, versionné à part
sortie: schemas/script.json      # la forme exacte de la réponse attendue

cache: oui                       # même entrée = ne repaie pas
sauvegarde: oui                  # point de reprise après plantage
demande_validation: oui          # ← s'arrête et m'attend ici
```

Le reste — les réessais, le cache, le comptage des coûts, les logs — est géré
automatiquement par le moteur. L'agent n'a pas à s'en occuper.

**Ajouter un agent** = 1 fichier de config + 1 prompt + ~30 lignes de code.

---

## Les 12 agents

### 🔍 Analyser une vidéo existante (5 agents)

| Agent | Ce qu'il fait | Avec quoi | Coût |
|---|---|---|---|
| **1 · Ingest** | Récupère la vidéo, la met au bon format (9:16, 30 img/s) | FFmpeg | 0 € |
| **2 · Transcription** | Écrit tout ce qui est dit, **avec le timing de chaque mot** | Whisper (Groq) | 0,001 € |
| **3 · Découpage** | Détecte chaque coupe, mesure la durée de chaque plan | PySceneDetect | **0 €** |
| **4 · Vision** | Regarde des images clés : cadrage, couleurs, texte à l'écran | Claude Haiku | 0,018 € |
| **5 · Son** | Mesure le BPM, l'énergie, les silences, le volume | librosa | **0 €** |

> **Les agents 3 et 5 ne coûtent rien.** Le rythme de montage et le BPM se **mesurent**
> avec des outils classiques. Beaucoup de projets envoient ça à une IA — c'est plus cher,
> plus lent, et moins précis. C'est un des choix qui font la différence sur la facture.

### 🧬 La recette virale (2 agents)

| Agent | Ce qu'il fait |
|---|---|
| **6 · Recette** | Rassemble tout ce que les 5 précédents ont trouvé, et en fait une fiche structurée |
| **7 · Nettoyage** | Retire **tout** le contenu identifiable : phrases, noms, marques. Il ne reste que le squelette réutilisable |

L'agent 7 n'est pas optionnel. Sans lui, ma bibliothèque contiendrait le travail des
autres. Avec lui, elle ne contient que des chiffres et des structures.

### ✍️ Créer (3 agents)

| Agent | Ce qu'il fait |
|---|---|
| **8 · Angle** | Mon idée brute → un point de vue précis, une promesse, une cible |
| **9 · Script** | Le texte scène par scène + 3 accroches concurrentes. Respecte le rythme imposé par la recette |
| **10 · Découpage visuel** | Chaque scène → une description d'image (même style partout, même graine aléatoire) |

### 🎬 Fabriquer (2 agents)

| Agent | Ce qu'il fait | Avec quoi |
|---|---|---|
| **11 · Assets** | Génère les images, la voix, choisit la musique, fabrique les sous-titres | FLUX + ElevenLabs + banque locale |
| **12 · Montage** | Assemble tout, vérifie que c'est correct (durée, son, lisibilité) | FFmpeg |

---

## Ce qui fait qu'une vidéo ressemble à une vraie vidéo

C'est là que ça se joue vraiment — pas dans l'architecture. Ce que l'agent 12 fait,
au-delà de coller les images bout à bout :

| Technique | Pourquoi c'est indispensable |
|---|---|
| **Zoom lent sur chaque image** (Ken Burns) | Sans mouvement, c'est un diaporama. Avec, c'est une vidéo. C'est LE truc qui change tout. |
| **Coupes calées sur le rythme de la musique** | On utilise le BPM mesuré par l'agent 5. Le cerveau le perçoit même sans le remarquer. |
| **Sous-titres karaoké mot à mot** | Le mot s'allume quand il est prononcé. Standard absolu sur TikTok. |
| **Volume normalisé (−14 LUFS)** | Une vidéo trop faible ou saturée est zappée en 1 seconde. |
| **Zones de sécurité respectées** | Le texte ne passe pas sous les boutons de l'interface TikTok. |
| **Transitions courtes** | Coupe franche par défaut, effet seulement sur les moments forts. |

**Avertissement honnête** : c'est le point le plus risqué du projet. Un enchaînement
d'images IA avec une voix synthétique peut être techniquement parfait et rester
inregardable. C'est pour ça que le plan ([06](./06-plan.md)) commence par **fabriquer
10 vidéos à la main** avant d'automatiser quoi que ce soit. Savoir ce qui marche
d'abord, automatiser ensuite.
