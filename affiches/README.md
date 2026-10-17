# Affiches métro nesoly

Affiches pour le métro parisien, avec le logo nesoly vectorisé.

Le logo nesoly est en crème (#F2EDE6) sur le marron nesoly (#3E2E31), avec le slogan « Réconfort olfactif ». Il n'y a rien d'autre sur l'affiche.

| Fichier | Format |
|---|---|
| `out/nesoly_affiche_paysage` | 4:3, pour le 4 × 3 m des couloirs (4800×3600 px) |
| `out/nesoly_affiche_portrait` | 120 × 176 cm (3600×5280 px) |

Chaque affiche existe en PNG et en PDF. Le PDF garde le logo et le slogan en vectoriel.

`out/mockup_couloir.jpg`, `out/mockup_quai.jpg` et `out/mockup_escalier.jpg` montrent les affiches en situation dans le métro.

```
cd affiches
pip install playwright opencv-python-headless potracer numpy pillow
python3 vectorize_logo.py      # nesoly_logo.svg à partir de animation/source/nesoly_logo.png
python3 build_affiches.py      # affiches PNG + PDF dans out/
python3 mockup_metro.py source/metro_couloir.jpg source/metro_quai.jpg source/metro_escalier.jpg
```

Le slogan, les tailles et les formats se règlent dans `minimal()` et `POSTERS`, dans `build_affiches.py`.
