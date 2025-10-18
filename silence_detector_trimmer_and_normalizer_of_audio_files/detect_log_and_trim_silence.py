import subprocess
import re
import os
import shlex

# Configuration
INPUT_ROOT_FOLDER = r"C:\Users\black\Desktop\audio_files"
DEST_OUT_FOLDER = r"./out_trimmed"
LOG_FILE = "detect_log_and_trim_silence_log.txt"

# Detection parameters
NOISE_LEVEL = -45   # Sensitivity of silence detection (more negative = more sensitive)
MIN_SILENCE = 2.0   # Duration (sec) required for ffmpeg to count as silence
SAFE_START_LIMIT = 2.5  # Only trim start if silence occurs before this
SAFE_END_LIMIT = 2.5    # Only trim end if silence is within this many seconds of the end
MIN_TRIM_SILENCE = 2.5  # Ignore detected silences shorter than this
MAX_SILENCE_TO_TRIM = 60.0  # Optional: ignore unrealistically long silence segments (e.g. bad detection)

# ------------------------------------------------------------
# TUNING GUIDE:
# ------------------------------------------------------------
# NOISE_LEVEL:
#     Controls sensitivity (default: -40 dB)
#     → More negative (-50) = more sensitive to faint sounds
#     → Less negative (-20) = only trims complete silence
#           -20 dB	Very strict silence detection — only counts truly silent (very quiet) parts	Detects less silence — 
#                                 ignores quiet ambience
#           
#           -40 dB	Moderate — counts both silence and soft fades or background noise	A good general balance for music
#           
#           -50 dB	Very sensitive — even faint hums, reverbs, or background air count as silence	Detects more silence 
#                                 (may trim too much if not careful)
#           
#           -60 dB	Extremely sensitive — almost anything below whisper level is considered silence	Best only for clean 
#                                 recordings or post-mastered speech
#
# MIN_SILENCE:
#     Minimum continuous duration (in seconds) to qualify as "silence."
#
# SAFE_START_LIMIT / SAFE_END_LIMIT:
#     Protect short intro/outro silences; higher = safer, fewer trims.
#
# MIN_TRIM_SILENCE:
#     Silences shorter than this are ignored (for stability).
#
# MAX_SILENCE_TO_TRIM:
#     Safety cap against faulty detections (e.g., blank files).
# ------------------------------------------------------------

# Preprocessing controls
USE_HIGHPASS = True      # Filter out sub-bass rumble before silence detection
USE_LOUDNORM = True      # Normalize loudness for consistent detection
USE_BANDPASS = True      # Apply both high-pass and low-pass filters for best accuracy (slower but safer)

HIGHPASS_FREQ = 200
'''
HIGHPASS_FREQ removes low-frequency rumble and bass before silence detection.

Things like:
subwoofer frequencies (<200 Hz),
mic pops, stage hum, foot thumps, or background vibrations.

These low sounds are often present even when a track is “silent,” and they can confuse ffmpeg into 
thinking there’s still sound.

So a high-pass filter makes silence detection more reliable without touching the musical mid and treble content.'''


LOWPASS_FREQ = 3000

'''
This removes high-frequency hiss and noise that can also prevent silence detection.

Things like:
tape hiss,
reverb tails with faint high tones,
air or wind noise.

By cutting everything above 3 kHz, we tell ffmpeg to “focus” on the core musical range (vocals, instruments, 
and midrange), which is where meaningful audio lives.

This helps it ignore ambience or reverberation that you don’t want to count as “sound.”
'''

# ------------------------------------------------------------
# PERFORMANCE NOTES:
# ------------------------------------------------------------
# Each enabled filter adds processing time:
#   - BANDPASS (highpass+lowpass): Most accurate, slower
#   - HIGHPASS only: Moderate accuracy, faster
#   - LOUDNORM: Improves consistency, adds ~2–3 seconds per file
#
# For large libraries:
#   - Disable LOUDNORM for faster runs
#   - Keep BANDPASS if quality and accuracy are priorities
# ------------------------------------------------------------

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

            # Build preprocessing chain
            pre_filters = []

            # ============================================================
            # BAND-PASS FILTER: combines high-pass and low-pass
            # ------------------------------------------------------------
            # • Removes inaudible low-frequency noise (hum, mic pops, bass rumble)
            # • Removes overly high frequencies (hiss, cymbals, reverb tails)
            # • Leaves only the “core” midrange content where most music energy exists (200–3000 Hz)
            # • Greatly improves silence detection accuracy on music with ambience or room noise
            # • Slightly slower because it processes two filters in sequence
            # ------------------------------------------------------------
            # Turn this OFF (USE_BANDPASS = False) if:
            #     - You’re processing speech or podcasts (you may want highs preserved)
            #     - You want faster runs at the cost of precision
            # ============================================================

            if USE_BANDPASS:
                pre_filters.append(f"highpass=f={HIGHPASS_FREQ}")
                pre_filters.append(f"lowpass=f={LOWPASS_FREQ}")
            else:
                # ============================================================
                # SIMPLE HIGH-PASS FILTER (used if band-pass is off)
                # ------------------------------------------------------------
                # • Keeps high frequencies intact, only removes deep bass rumble
                # • Faster, less CPU usage, but may detect some false “sound” from reverb/hiss
                # ------------------------------------------------------------
                # Use this mode if:
                #     - You want faster analysis
                #     - You’re trimming spoken word or podcasts
                # ============================================================
                if USE_HIGHPASS:
                    pre_filters.append(f"highpass=f={HIGHPASS_FREQ}")

            # ============================================================
            # LOUDNESS NORMALIZATION
            # ------------------------------------------------------------
            # • Makes all tracks analyzed at similar loudness (-23 LUFS target)
            # • Prevents ffmpeg from missing quiet silences in very loud songs
            # • Adds a few seconds to processing but stabilizes detection
            # ------------------------------------------------------------
            # You can disable (USE_LOUDNORM = False) if:
            #     - Your library is already volume-normalized (modern mastered albums)
            #     - You need faster performance
            # ============================================================
            if USE_LOUDNORM:
                pre_filters.append("loudnorm=I=-23:TP=-1.5:LRA=11")

            # Append silence detection filter
            pre_chain = ",".join(pre_filters + [f"silencedetect=noise={NOISE_LEVEL}dB:d={MIN_SILENCE}"])

            # Run silencedetect with preprocessing
            
            # Creating cmd command
            cmd = [
                "ffmpeg", "-hide_banner", "-nostats",
                "-i", path,
                "-af", pre_chain,
                "-f", "null", "-"
            ]

            try:
                # Run ffmpeg process for silence detection
                result = subprocess.run(
                    cmd,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace"
                )
            except Exception as e:
                # Except any errors that may have occured while running ffmpeg process
                print(f"Error analyzing {fname}: {e}")
                continue
            
            # Filtering the results received from ffmpeg
            starts = [float(x) for x in re_start.findall(result.stderr)]
            ends = [float(x) for x in re_end.findall(result.stderr)]

            if not starts or not ends:
                print(" No silence detected")
                log.write(f"[NO SILENCE] {rel_path}\n")
                continue

            # Pair up and filter silences
            silence_pairs = list(zip(starts, ends))
            filtered_pairs = [
                (s, e)
                for s, e in silence_pairs
                if MIN_TRIM_SILENCE <= (e - s) <= MAX_SILENCE_TO_TRIM
            ]

            if not filtered_pairs:
                print("  All detected silences ignored (too short or too long)")
                log.write(f"[IGNORED SILENCE] {rel_path}\n")
                continue

            starts = [s for s, _ in filtered_pairs]
            ends = [e for _, e in filtered_pairs]

            print(f"  → Detected {len(starts)} significant silences (≥ {MIN_TRIM_SILENCE}s)")

            # Determine safe trim points
            start_trim = 0.0
            end_trim = None

            # ------------------------------------------------------------
            # SILENCE VALIDATION LOGIC
            # ------------------------------------------------------------
            # We only trim silence at:
            #   - The very beginning (SAFE_START_LIMIT window)
            #   - The very end (SAFE_END_LIMIT or 85%+ of track length)
            #
            # This ensures that musical silence or artistic pauses
            # in the *middle* of the track are never trimmed.
            # ------------------------------------------------------------

            # Check silence at start
            if starts[0] < SAFE_START_LIMIT and ends[0] < 10:
                start_trim = ends[0]
                print(f"  Safe to trim start up to {start_trim:.2f}s")

            # Check silence at end
            
            # Preparing cmd command
            cmd_probe = [
                "ffprobe", "-v", "error", "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1", path
            ]
            try:
                # Run the ffprobe process
                duration_str = subprocess.check_output(cmd_probe, text=True).strip()
                duration = float(duration_str)
            except Exception:
                # Except any errors that may have occured while running ffprobe process
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
                    print(f"  Safe to trim end (starts {distance_to_end:.2f}s before end, len={silence_len:.2f}s)")

                # Case B: Silence covers big part of the ending
                elif silence_len >= MIN_TRIM_SILENCE and last_silence_end >= (duration * 0.85):
                    end_trim = last_silence_start
                    print(f"  Trimming extended silence in final section "
                          f"(starts at {last_silence_start:.2f}s, len={silence_len:.2f}s, track={duration:.2f}s)")

            # Prepare output
            out_path = os.path.join(DEST_OUT_FOLDER, rel_path)
            os.makedirs(os.path.dirname(out_path), exist_ok=True)

            # Check if trimming is required
            if start_trim == 0.0 and end_trim is None:
                print("  Keeping original (no safe trim needed)")
                log.write(f"[KEEP ORIGINAL] {rel_path}\n")
                continue
            
            # Build the trim command
            cmd_trim = ["ffmpeg", "-hide_banner", "-nostats", "-y"]
            
            # Appending the trim start point
            if start_trim > 0:
                cmd_trim += ["-ss", str(start_trim)]
            cmd_trim += ["-i", path]
            
            # Appending the trim end point
            if end_trim:
                if start_trim > 0:
                    duration_out = end_trim - start_trim
                    if duration_out <= 0:
                        print(f"  Skipping (negative duration {duration_out:.2f}s)")
                        log.write(f"[SKIPPED - BAD DURATION] {rel_path}\n")
                        continue
                    cmd_trim += ["-t", f"{duration_out:.2f}"]
                else:
                    cmd_trim += ["-to", str(end_trim)]
            
            # Appending the outputting location
            cmd_trim += [out_path]

            print("     Running safe trim:", " ".join(shlex.quote(c) for c in cmd_trim))

            try:
                # Run the ffmpeg process for trimming audio file
                subprocess.run(cmd_trim, check=True)
                log.write(f"[TRIMMED] {rel_path} (start={start_trim:.2f}, end={end_trim})\n")
            
            except subprocess.CalledProcessError:
                # Excepting error in the ffmpeg process while trimming
                print(f"      Failed to trim {rel_path}")
                log.write(f"[TRIM FAILED] {rel_path}\n")

    print(f"\n Done! Log saved to {LOG_FILE}")

# The log file records each file’s result:
# [NO SILENCE] — no silent regions found
# [IGNORED SILENCE] — detected silences didn’t meet trim rules
# [KEEP ORIGINAL] — silence detected but trimming not applied
# [TRIMMED] — file successfully trimmed
# [TRIM FAILED] — ffmpeg trim command failed
