# Affiches métro nesoly

Ces affiches reprennent les codes des campagnes du métro parisien et portent le logo nesoly vectorisé.

| Fichier | Format | Style |
|---|---|---|
| `out/nesoly_affiche_expo_paysage` | 4:3, pour le 4 × 3 m des couloirs (4800×3600 px) | éditorial « exposition » : logo, deux photos, titre « Sentir bon, / sans parfum » |
| `out/nesoly_affiche_expo_portrait` | 120 × 176 cm (3600×5280 px) | même style avec une photo : « Rayonner sans crier » |
| `out/nesoly_affiche_rituel_paysage` | 4:3 (4800×3600 px) | publicité produit : photo pleine page, accroche « 6 à 10 h », le rituel en 4 étapes |

Chaque affiche existe en PNG et en PDF. Le PDF garde le logo et les textes en vectoriel.

`out/mockup_couloir.jpg` et `out/mockup_quai.jpg` montrent les affiches en situation dans le métro.

```
cd affiches
pip install playwright opencv-python-headless potracer numpy pillow
python3 vectorize_logo.py      # nesoly_logo.svg à partir de animation/source/nesoly_logo.png
python3 build_affiches.py      # affiches PNG + PDF dans out/
python3 mockup_metro.py source/metro_couloir.jpg source/metro_quai.jpg
```

Les textes et la mise en page se modifient dans `build_affiches.py`. Il y a un bloc HTML/CSS par affiche. Les photos viennent de `animation/sans_parfum/photos/`.

Ces photos ne font qu'environ 740 px de large. Elles suffisent pour l'écran et les maquettes, mais pas pour une impression en 4 × 3 m. Avant l'impression, il faut les remplacer par les fichiers HD sous le même nom, puis relancer `build_affiches.py`.
