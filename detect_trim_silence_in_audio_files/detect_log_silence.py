import subprocess
import re
import os

# --- Configuration ---
ROOT_FOLDER = r"D:\music all\music"  # root folder to scan recursively
NOISE_LEVEL = -50   # dB threshold (more negative = more sensitive)
MIN_SILENCE = 3.0   # seconds of silence to count
LOG_FILE = "silence_log.txt"

# --- Regex to capture silencedetect output ---
silence_re = re.compile(r"silence_start")

# --- Prepare log file ---
with open(LOG_FILE, "w", encoding="utf-8") as log:
    log.write("Silence detection results\n")
    log.write("=========================\n\n")

    # Walk recursively through all folders
    for root, _, files in os.walk(ROOT_FOLDER):
        for fname in files:
            if not fname.lower().endswith((".mp3", ".wav", ".flac", ".m4a")):
                continue

            path = os.path.join(root, fname)
            print(f"Analyzing: {path}")

            # Run ffmpeg silencedetect
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats",
                "-i", path,
                "-af", f"silencedetect=noise={NOISE_LEVEL}dB:d={MIN_SILENCE}",
                "-f", "null", "-"
            ]

            try:
                result = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.DEVNULL, text=True)
            except Exception as e:
                print(f" Error analyzing {fname}: {e}")
                continue

            matches = silence_re.findall(result.stderr)

            if matches:
                print(f"  → SILENCE FOUND ({len(matches)} segments)")
                log.write(f"[SILENCE FOUND] {path}\n")
            else:
                print(f"  → No silence detected")

    print(f"\nDone! Results saved to {os.path.abspath(LOG_FILE)}")
