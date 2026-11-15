# video-madgic

Vidéo promotionnelle **verticale (TikTok / Reels / Shorts, 1080×1920, 30 fps)** pour **madgic** — la boutique d'informations qui explique comment utiliser toutes les IA (ChatGPT, Claude, Midjourney…) ainsi qu'un agent très poussé, **gratuitement**, via Arena AI.

## Histoire racontée

1. **Chapitre 1 — La recherche** : un jeune homme africain, la nuit, cherche des réponses sur internet et les IA.
2. **Le problème** : les meilleurs outils sont payants (20 €, 30 €, 99 € / mois) — « TOUT EST PAYANT. »
3. **La notification** : « Passez à la version Pro. » — la porte se referme.
4. **Le déclic** : il découvre **madgic**.
5. **madgic** : toutes les IA réunies, un agent très poussé inclus — **0,00 € / mois, pour toujours.**
6. **CTA** : « Cherche *madgic* ».

## Structure

- `timeline.py` — source unique de la timeline (durée de chaque scène VO + gaps).
- `synth_music.py` — bande-son ambient synthétisée (nappe + arpège, numpy).
- `build_audio.py` — mixe la voix off + la musique via ffmpeg → `assets/audio/mix.wav`.
- `render.py` — moteur de motion design (PIL, 8 scènes) → encode `madgic_promo.mp4`.
- `assets/vo/*.mp3` — voix off française (8 plans).
- `assets/img/*.jpg` — visuels générés par IA (jeune homme africain).
- `assets/fonts/*.ttf` — Anton + Montserrat.

## Reconstruire la vidéo

```bash
python3 -m venv .venv && .venv/bin/pip install moviepy pillow numpy
.venv/bin/python synth_music.py
.venv/bin/python timeline.py && .venv/bin/python build_audio.py
.venv/bin/python render.py          # rendu complet (~10 min)
SAMPLE_TIMES="2,20,40,52" .venv/bin/python render.py   # images de contrôle uniquement
```

Livrable final : `madgic_promo.mp4` (généré, non versionné).
