import subprocess
import re
import os
import shlex

# --- Configuration ---
INPUT_ROOT_FOLDER = r"D:\music all\music"
DEST_OUT_FOLDER = r"./out_trimmed"
LOG_FILE = "silence_trimming_log.txt"

# Detection parameters
NOISE_LEVEL = -50
MIN_SILENCE = 2.5  # detect shorter silences
SAFE_START_LIMIT = 3.0  # don't trim if first sound starts after 3 sec
SAFE_END_LIMIT = 3.0    # don't trim if last silence is within 3 sec of end

# Regex for silence detection
re_start = re.compile(r"silence_start: ([0-9.]+)")
re_end = re.compile(r"silence_end: ([0-9.]+)")

# --- Prepare log file ---
with open(LOG_FILE, "w", encoding="utf-8") as log:
    log.write("Silence detection and safe trimming results\n")
    log.write("===========================================\n\n")

    for root, _, files in os.walk(INPUT_ROOT_FOLDER):
        for fname in files:
            if not fname.lower().endswith((".mp3", ".wav", ".flac", ".m4a")):
                continue

            path = os.path.join(root, fname)
            rel_path = os.path.relpath(path, INPUT_ROOT_FOLDER)
            print(f"\nAnalyzing: {rel_path}")

            # --- Run silencedetect ---
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats",
                "-i", path,
                "-af", f"silencedetect=noise={NOISE_LEVEL}dB:d={MIN_SILENCE}",
                "-f", "null", "-"
            ]

            try:
                result = subprocess.run(
                    cmd,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
            except Exception as e:
                print(f"Error analyzing {fname}: {e}")
                continue

            starts = [float(x) for x in re_start.findall(result.stderr)]
            ends = [float(x) for x in re_end.findall(result.stderr)]

            if not starts or not ends:
                print("  → No silence detected")
                log.write(f"[NO SILENCE] {rel_path}\n")
                continue

            print(f"  → Detected {len(starts)} silent sections")

            # --- Determine safe trim points ---
            start_trim = 0.0
            end_trim = None

            # Case 1: Silence at the very start (before music)
            if starts[0] < SAFE_START_LIMIT and ends[0] < 10:
                start_trim = ends[0]
                print(f"  → Safe to trim start up to {start_trim:.2f}s")

            # Case 2: Silence near or at the end
            # Determine total duration first (to check how close silence is to the end)
            cmd_probe = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path
            ]
            try:
                duration_str = subprocess.check_output(cmd_probe, text=True).strip()
                duration = float(duration_str)
            except Exception:
                duration = None

            if duration:
                last_silence_start = starts[-1]
                last_silence_end = ends[-1]

                # If silence starts close to the end of the track, trim from there
                if duration - last_silence_start <= SAFE_END_LIMIT:
                    end_trim = last_silence_start
                    print(f"  → Safe to trim end starting at {end_trim:.2f}s (track length: {duration:.2f}s)")


            # --- Prepare output ---
            out_path = os.path.join(DEST_OUT_FOLDER, rel_path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            # --- Build trim command ---
            if start_trim == 0.0 and end_trim is None:
                print("  → Keeping original (no safe trim needed)")
                log.write(f"[KEEP ORIGINAL] {rel_path}\n")
                continue

            cmd_trim = ["ffmpeg", "-hide_banner", "-nostats", "-y"]

            # Set start position (if any)
            if start_trim > 0:
                cmd_trim += ["-ss", str(start_trim)]

            cmd_trim += ["-i", path]

            # If we have a valid end trim, convert to duration if we also have a start trim
            if end_trim:
                if start_trim > 0:
                    # Calculate duration from start to end
                    duration_out = end_trim - start_trim
                    if duration_out <= 0:
                        print(f"  ⚠ Skipping: computed negative duration ({duration_out:.2f}s)")
                        log.write(f"[SKIPPED - BAD DURATION] {rel_path}\n")
                        continue
                    cmd_trim += ["-t", f"{duration_out:.2f}"]
                else:
                    cmd_trim += ["-to", str(end_trim)]

            cmd_trim += [out_path]

            print("     Running safe trim:", " ".join(shlex.quote(c) for c in cmd_trim))

            try:
                subprocess.run(cmd_trim, check=True)
                log.write(f"[TRIMMED] {rel_path} (start={start_trim:.2f}, end={end_trim})\n")
            except subprocess.CalledProcessError:
                print(f"      Failed to trim {rel_path}")
                log.write(f"[TRIM FAILED] {rel_path}\n")

    print(f"\n Done! Log saved to {LOG_FILE}")
