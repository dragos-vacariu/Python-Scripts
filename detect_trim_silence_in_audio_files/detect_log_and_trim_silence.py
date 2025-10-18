import subprocess
import re
import os
import shlex

# --- Configuration ---
INPUT_ROOT_FOLDER = r"C:\Users\black\Desktop\audio_files"
DEST_OUT_FOLDER = r"./out_trimmed"
LOG_FILE = "silence_trimming_log.txt"

# --- Detection parameters ---
NOISE_LEVEL = -40   # Sensitivity of silence detection (more negative = more sensitive)
MIN_SILENCE = 2.0   # Duration (sec) required for ffmpeg to count as silence
SAFE_START_LIMIT = 2.5  # Only trim start if silence occurs before this
SAFE_END_LIMIT = 2.5    # Only trim end if silence is within this many seconds of the end
MIN_TRIM_SILENCE = 2.5  # Ignore detected silences shorter than this
MAX_SILENCE_TO_TRIM = 60.0  # Optional: ignore unrealistically long silence segments (e.g. bad detection)

# --- Preprocessing controls ---
USE_HIGHPASS = True      # Filter out sub-bass rumble before silence detection
USE_LOUDNORM = True      # Normalize loudness for consistent detection

# Regex for silence detection
re_start = re.compile(r"silence_start: ([0-9.]+)")
re_end = re.compile(r"silence_end: ([0-9.]+)")

# --- Prepare log file ---
with open(LOG_FILE, "w", encoding="utf-8") as log:
    log.write("Enhanced silence detection and safe trimming results\n")
    log.write("====================================================\n\n")

    for root, _, files in os.walk(INPUT_ROOT_FOLDER):
        for fname in files:
            if not fname.lower().endswith((".mp3", ".wav", ".flac", ".m4a")):
                continue

            path = os.path.join(root, fname)
            rel_path = os.path.relpath(path, INPUT_ROOT_FOLDER)
            print(f"\nAnalyzing: {rel_path}")

            # --- Build preprocessing chain ---
            pre_filters = []
            if USE_HIGHPASS:
                pre_filters.append("highpass=f=200")  # remove low rumble
            if USE_LOUDNORM:
                pre_filters.append("loudnorm=I=-23:TP=-1.5:LRA=11")  # normalize volume
            pre_chain = ",".join(pre_filters + [f"silencedetect=noise={NOISE_LEVEL}dB:d={MIN_SILENCE}"])

            # --- Run silencedetect with preprocessing ---
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats",
                "-i", path,
                "-af", pre_chain,
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

            # --- Pair up and filter silences ---
            silence_pairs = list(zip(starts, ends))
            filtered_pairs = [
                (s, e)
                for s, e in silence_pairs
                if MIN_TRIM_SILENCE <= (e - s) <= MAX_SILENCE_TO_TRIM
            ]

            if not filtered_pairs:
                print("  → All detected silences ignored (too short or too long)")
                log.write(f"[IGNORED SILENCE] {rel_path}\n")
                continue

            starts = [s for s, _ in filtered_pairs]
            ends = [e for _, e in filtered_pairs]

            print(f"  → Detected {len(starts)} significant silences (≥ {MIN_TRIM_SILENCE}s)")

            # --- Determine safe trim points ---
            start_trim = 0.0
            end_trim = None

            # Check silence at start
            if starts[0] < SAFE_START_LIMIT and ends[0] < 10:
                start_trim = ends[0]
                print(f"  → Safe to trim start up to {start_trim:.2f}s")

            # Check silence at end
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
                silence_len = last_silence_end - last_silence_start

                # How close to the end the silence starts
                distance_to_end = duration - last_silence_start

                # Case A: Silence is very close to the end (within SAFE_END_LIMIT)
                if distance_to_end <= SAFE_END_LIMIT:
                    end_trim = last_silence_start
                    print(f"  → Safe to trim end (starts {distance_to_end:.2f}s before end, len={silence_len:.2f}s)")

                # Case B: Silence covers big part of the ending
                elif silence_len >= MIN_TRIM_SILENCE and last_silence_end >= (duration * 0.85):
                    end_trim = last_silence_start
                    print(f"  → Trimming extended silence in final section "
                          f"(starts at {last_silence_start:.2f}s, len={silence_len:.2f}s, track={duration:.2f}s)")

            # --- Prepare output ---
            out_path = os.path.join(DEST_OUT_FOLDER, rel_path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            # --- Build trim command ---
            if start_trim == 0.0 and end_trim is None:
                print("  → Keeping original (no safe trim needed)")
                log.write(f"[KEEP ORIGINAL] {rel_path}\n")
                continue

            cmd_trim = ["ffmpeg", "-hide_banner", "-nostats", "-y"]
            if start_trim > 0:
                cmd_trim += ["-ss", str(start_trim)]
            cmd_trim += ["-i", path]
            if end_trim:
                if start_trim > 0:
                    duration_out = end_trim - start_trim
                    if duration_out <= 0:
                        print(f"  ⚠ Skipping (negative duration {duration_out:.2f}s)")
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
