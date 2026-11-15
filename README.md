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

Livrables :
- `madgic_promo.mp4` — master vertical 9:16 (versionné pour la pérennité).
- `madgic_promo_poster.jpg` — miniature/affiche (versionnée).
- `madgic_promo_16x9.mp4` / `madgic_promo_1x1.mp4` — variantes centrées sur fond flou (non versionnées ; régénérer depuis le master) :

```bash
FF=$(python3 -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())")  # ou via le venv
$FF -y -loglevel error -i madgic_promo.mp4 -filter_complex \
  "[0:v]split[bg][fg];[bg]scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,gblur=sigma=30,eq=brightness=-0.28:saturation=0.8[bgb];[fg]scale=-2:1080[fgs];[bgb][fgs]overlay=(W-w)/2:0[v]" \
  -map "[v]" -map 0:a -c:v libx264 -crf 22 -pix_fmt yuv420p -c:a copy madgic_promo_16x9.mp4
# idem avec 1080:1080 / crop=1080:1080 pour le carré 1:1
```

Légendes et hashtags prêts à coller : voir `SOCIAL.md`.
