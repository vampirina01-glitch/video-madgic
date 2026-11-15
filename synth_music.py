"""Synthesize a soft cinematic ambient track for the MADGIC promo video."""
import numpy as np
import wave

SR = 48000
TOTAL = 55.0
t = np.arange(int(SR * TOTAL)) / SR

def note(f, dur, kind="pad"):
    n = int(SR * dur)
    tt = np.arange(n) / SR
    if kind == "pad":
        env = np.minimum(tt / 1.1, 1.0) * np.minimum((dur - tt) / 1.6, 1.0)
        x = (np.sin(2 * np.pi * f * tt)
             + 0.42 * np.sin(2 * np.pi * f * 2 * tt + 0.3)
             + 0.18 * np.sin(2 * np.pi * f * 3.01 * tt)
             + 0.25 * np.sin(2 * np.pi * (f * 1.003) * tt))
        return x * env
    # music box / kalimba
    env = np.exp(-tt * 3.4) * np.minimum(tt / 0.008, 1.0)
    return (np.sin(2 * np.pi * f * tt)
            + 0.55 * np.sin(2 * np.pi * f * 4 * tt) * np.exp(-tt * 6)
            + 0.22 * np.sin(2 * np.pi * f * 7.1 * tt) * np.exp(-tt * 9)) * env

def lowpass(x, a=0.09):
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc += a * (v - acc)
        y[i] = acc
    return y

mix = np.zeros_like(t)

# Pad: Am – F – C – G progression
chords = [
    ([110.00, 130.81, 164.81, 220.00], 0.0, 8.0),    # Am
    ([ 87.31, 110.00, 130.81, 174.61], 6.5, 8.0),    # F
    ([ 98.00, 130.81, 164.81, 196.00], 13.0, 8.0),   # C (G bass feel)
    ([ 98.00, 123.47, 146.83, 196.00], 19.5, 8.0),   # G
    ([110.00, 130.81, 164.81, 220.00], 26.0, 9.0),   # Am (lift)
    ([ 87.31, 110.00, 130.81, 174.61], 33.0, 9.0),   # F
    ([ 98.00, 123.47, 146.83, 246.94], 40.0, 15.0),  # G sus
]
for freqs, start, dur in chords:
    seg = np.zeros(int(SR * dur))
    for f in freqs:
        seg += note(f, dur, "pad") * 0.16
    seg[:int(SR * dur)] = lowpass(seg, 0.10)
    i0 = int(SR * start)
    mix[i0:i0 + len(seg)] += seg[:len(mix) - i0]

# Music-box arpeggio after the discovery (~t = 30s)
arp_notes = [440.00, 523.25, 659.25, 880.00, 659.25, 523.25,
             440.00, 349.23, 392.00, 523.25, 587.33, 659.25]
start, step = 30.0, 0.42
for k, f in enumerate(arp_notes * 2):
    i0 = int(SR * (start + k * step))
    if i0 >= len(mix):
        break
    seg = note(f, 1.6, "box") * 0.085
    mix[i0:i0 + len(seg)] += seg[:len(mix) - i0]

# Soft noise swell at the flash moment (~t = 29.3s)
i0 = int(SR * 28.6)
swell_len = int(SR * 1.8)
sweep = np.random.default_rng(7).normal(0, 1, swell_len)
sweep *= np.hanning(swell_len) ** 1.5
sweep = lowpass(sweep, 0.25) * 0.22
mix[i0:i0 + swell_len] += sweep[:len(mix) - i0]

mix = np.tanh(mix * 1.15)
mix *= 0.42 / (np.max(np.abs(mix)) + 1e-9)
mix *= 0.9
# fade in / out
fi, fo = int(SR * 1.2), int(SR * 2.4)
mix[:fi] *= np.linspace(0, 1, fi)
mix[-fo:] *= np.linspace(1, 0, fo)

stereo = np.stack([mix, np.roll(mix, int(SR * 0.012))], axis=1)
stereo *= 0.85
pcm = (stereo * 32767 * 0.8).astype(np.int16)
with wave.open("assets/audio/music.wav", "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())
print("music written", TOTAL, "s")
