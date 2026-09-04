## Mesure des vidéos rendues

*Aucun appel réseau : ffmpeg et un compteur de pixels.*

| plan | format | durée | attendue | couleurs à l'écran | verdict |
|---|---|---|---|---|---|
| 01 | 704×1248 | 10.2s | 10.138s | orange 80% · vert 8% · bleu 6% | 1 point(s) |
| 03 | 704×1248 | 10.2s | 9.131s | bleu 53% · rouge 28% · cyan 19% | 1 point(s) |
| 05 | 704×1248 | 10.2s | 8.915s | bleu 95% | 2 point(s) |
| 07 | 704×1248 | 10.2s | 8.987s | vert 43% · cyan 30% · bleu 27% | 2 point(s) |
| 08 | 704×1248 | 10.2s | 9.85s | bleu 45% · rouge 23% · cyan 14% | 1 point(s) |

**Plan 01** — shot_01.mp4
  · le plan annonce du rouge, la vidéo en porte 1.1% — la notion n'est portée par rien

**Plan 03** — shot_03.mp4
  · 10.2s rendues pour 9.131s prévues (+1.1s)

**Plan 05** — shot_05.mp4
  · 10.2s rendues pour 8.915s prévues (+1.3s)
  · le plan annonce du rouge, la vidéo en porte 0.7% — la notion n'est portée par rien

**Plan 07** — shot_07.mp4
  · 10.2s rendues pour 8.987s prévues (+1.3s)
  · le plan annonce du rouge, la vidéo en porte 0.1% — la notion n'est portée par rien

**Plan 08** — shot_08.mp4
  · le plan annonce du vert, la vidéo en porte 2.3% — la notion n'est portée par rien

