"""Single source of truth for the video timeline (used by audio build + renderer)."""
import json, os

# VO clip durations measured with moviepy (seconds)
VO = {"01": 7.08, "02": 8.10, "03": 2.86, "04": 4.13,
      "05": 2.60, "06": 7.21, "07": 5.58, "08": 7.34}

# (scene_key, vo_key, lead_before_vo, tail_after_vo, gap_after_scene)
TABLE = [
    ("s1_intro",     "01", 0.35, 0.15, 0.40),
    ("s2_search",    "02", 0.35, 0.30, 0.40),
    ("s3_prices",    "03", 0.35, 0.25, 0.40),
    ("s4_notif",     "04", 0.35, 0.30, 0.45),
    ("s5_discovery", "05", 0.30, 0.50, 0.35),
    ("s6_product",   "06", 0.45, 0.30, 0.40),
    ("s7_benefits",  "07", 0.35, 0.30, 0.45),
    ("s8_cta",       "08", 0.40, 1.70, 0.00),
]

def build():
    scenes, t = [], 0.0
    for key, vo, lead, tail, gap in TABLE:
        dur = lead + VO[vo] + tail
        # scene stays on screen during the inter-scene gap (visuals hold, no dead frames)
        scenes.append({
            "key": key, "vo": f"assets/vo/{vo}_*.mp3".replace("*", {
                "01": "intro", "02": "prices", "03": "paywall",
                "04": "notification", "05": "discovery", "06": "product",
                "07": "benefits", "08": "cta"}[vo]),
            "start": round(t, 3), "duration": round(dur + gap, 3),
            "vo_start": round(t + lead, 3), "vo_end": round(t + lead + VO[vo], 3),
        })
        t += dur + gap
    return {"scenes": scenes, "total": round(t - TABLE[-1][4], 3)}

TIMELINE = build()

if __name__ == "__main__":
    os.makedirs("assets/build", exist_ok=True)
    with open("assets/build/timeline.json", "w") as f:
        json.dump(TIMELINE, f, indent=2, ensure_ascii=False)
    for s in TIMELINE["scenes"]:
        print(f'{s["key"]:14s} start={s["start"]:6.2f} dur={s["duration"]:6.2f} vo@{s["vo_start"]:6.2f}')
    print("TOTAL", TIMELINE["total"], "s")
