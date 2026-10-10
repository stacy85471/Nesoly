# Animations nesoly

## Reel « fatigue olfactive » (TikTok / Instagram Reels)

`nesoly_reel_fatigue_olfactive.mp4`, en 1080×1920 et 30 i/s, dure 41 s, sans piste audio. Elle est prévue pour qu'on pose la voix off par-dessus.

| Séquence | Début | Fin | Texte |
|---|---|---|---|
| 1. Le piège du nez habitué | 0:00 | 0:09 | Titre, puis « Deux vaporisations… » à 0:02, puis « La fatigue olfactive… » à 0:04 |
| 2. Le cercle vicieux | 0:09 | 0:18 | Titre, puis « Deux pulvérisations de plus… » à 0:11, puis « Huit vaporisations… » à 0:14 |
| 3. La solution : Confiance et Rituels | 0:18 | 0:25 | Titre, puis « Un parfum de qualité tient 6 à 10 heures » à 0:21 |
| 4. Le Rituel en 4 étapes | 0:25 | 0:36 | Les étapes apparaissent à 0:27, 0:29, 0:31 et 0:33 |
| Logo nesoly | 0:36 | 0:41 | |

Les durées se règlent dans `SCENES` et l'apparition des textes dans `TEXTS`, tous deux dans `render_reel.py`.

```
cd animation
pip install numpy pillow scipy
python3 render_reel.py source/nesoly_logo.png nesoly_reel_fatigue_olfactive.mp4
python3 render_reel.py source/nesoly_logo.png /tmp/apercu --preview   # quelques images PNG
```

## Logo animé

Le logo animé seul se génère avec `render_logo.py`, qui produit `nesoly_logo_16x9.mp4` et `nesoly_logo_9x16.mp4`.

Polices : Cormorant Garamond et Jost, toutes deux sous licence SIL OFL (voir `fonts/`).
