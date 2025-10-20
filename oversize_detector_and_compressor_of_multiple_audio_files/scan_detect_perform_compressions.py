import os
import math
import datetime
import shutil
import subprocess
from mutagen import File as AudioFile

# ========================== CONFIGURATION ==========================
AUDIO_EXTENSIONS = ('.mp3', '.wav', '.aac', '.flac', '.ogg', '.m4a')

# this value can be tailored for more strict or less strict detections
# TOLERANCE should never go below 1.0. If the TOLERANCE would go below 1, you risk attempting to compressing files which cannot be reduced in size any longer.
TOLERANCE = 1.005 #try to keep it between 1.005 and 1.25 where 1.005 is very strict detection.

#THE COMPRESSION ALGORITHM WILL WORK SAME WAY REGARDLESS OF THE VALUE OF THE TOLERANCE. 
#THE ONLY DIFFERENCE IS WHICH FILES GET DETECTED AS OVERSIZE AND WHICH DOESN'T.

#The root directory to be scanned for audio files
INPUT_ROOT_DIR = r"D:\music all\music 6 (also new)"

#An output directory where backups for the detected files will be stored
ORIGINAL_BACKUPS_OUT_DIR = r".\Audio_Originals_Backup"

#An output directory where the resulted compressed files will be stored
COMPRESSED_OUT_DIR = r".\Audio_Compressed"

#Target bitrate for the compression of the audio files
TARGET_BITRATE = "128k"


#Flags controlling the features of the scripts

#turn this to true if you want the actions to be logged into a txt file
LOG_ONLY_FLAGGED = True 

#turn this to true if you want the script to attempt a compression for the detected oversized files
ATTEMPT_COMPRESSION = True 
# ===================================================================

timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_FILE = f"audio_compression_log_{timestamp}.txt"


def analyze_audio(file_path):
    """Extracts metadata and computes expected vs actual size."""
    
    #Opening audio file using mutagen and storing the file's metadata to variables
    audio = AudioFile(file_path)
    if not audio or not audio.info:
        #if the file is not an audio file
        return None
    
    #Read and store the metadata
    duration = audio.info.length
    bitrate = getattr(audio.info, "bitrate", None)
    if bitrate is None or bitrate == 0:
        #if the bitrate is not specified within the metadata
        return None
    
    #calculate the bitrate in kpbs
    bitrate_kbps = bitrate / 1000
    
    #calculate an expected size based on the bitrate
    expected_size_mb = (bitrate_kbps * duration) / (8 * 1024)
    actual_size_mb = os.path.getsize(file_path) / (1024 * 1024)
    
    #checking if the file would need a compression
    needs_compression = actual_size_mb > expected_size_mb * TOLERANCE
    
    #returning data
    return {
        "file": file_path,
        "duration_sec": round(duration, 2),
        "bitrate_kbps": round(bitrate_kbps, 2),
        "actual_size_mb": round(actual_size_mb, 2),
        "expected_size_mb": round(expected_size_mb, 2),
        "needs_compression": needs_compression,
    }


def scan_directory(root_dir):
    '''This function will scan the given directory and for each file in the directory will call analyze_audio'''
    results = []
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.lower().endswith(AUDIO_EXTENSIONS):
                file_path = os.path.join(root, file)
                info = analyze_audio(file_path)
                if info:
                    #if the file was an audio file then append it to the results
                    results.append(info)
    return results


def get_output_extension_and_codec(input_ext):
    """Choose output extension and codec for compression."""
    input_ext = input_ext.lower()
    if input_ext in ('.wav', '.flac'):
        # Convert lossless to MP3
        return '.mp3', 'libmp3lame'
    elif input_ext in ('.aac', '.m4a'):
        return '.m4a', 'aac'
    elif input_ext in ('.ogg',):
        return '.ogg', 'libvorbis'
    else:
        # Default: re-encode MP3s to smaller bitrate
        return '.mp3', 'libmp3lame'



def compress_with_ffmpeg(src_path, dest_path, bitrate, codec):
    """Use FFmpeg to compress an audio file to a specific bitrate and codec.
    The compression will remove and cover-art that may be used for the thumbnail of the file.
    """
    
    #Creating the directories for the output
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    #Creating the cmd command for the ffmpeg compression
    cmd = [
        "ffmpeg", "-y",
        "-i", src_path,
        "-map", "0:a",          # keep only audio streams
        "-vn",                  # disable video
        "-c:a", codec,          # set codec
        "-b:a", bitrate,        # target bitrate
        "-ar", "44100",         # resample
        "-ac", "2",             # stereo
        "-movflags", "+faststart",
        dest_path
    ]

    print(f"\nRunning FFmpeg: {' '.join(cmd)}")

    #Attempt to run the ffmpeg command to perform the compression
    try:
        subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        if os.path.exists(dest_path):
            new_size = os.path.getsize(dest_path) / (1024 * 1024)
            print(f"✅ Output size: {new_size:.2f} MB")
        else:
            print("⚠️ No output file created.")
        return True
    
    except subprocess.CalledProcessError as e:
        #If there was any exception thrown while attempting compression
        print(f"⚠️ FFmpeg error compressing {src_path}:\n{e.stderr.decode(errors='ignore')[:500]}")
        return False


def handle_flagged_files(results):
    """Backs up and compresses flagged files."""
    flagged_files = [r for r in results if r["needs_compression"]]
    
    if not flagged_files:
        print("\nNo flagged files found.")
        return

    print(f"\nProcessing {len(flagged_files)} flagged files...")

    for r in flagged_files:
        src_path = r["file"]
        rel_path = os.path.relpath(src_path, INPUT_ROOT_DIR)
        src_ext = os.path.splitext(src_path)[1]

        # Backup original file
        backup_dest = os.path.join(ORIGINAL_BACKUPS_OUT_DIR, rel_path)
        
        # Creating the backup directory
        os.makedirs(os.path.dirname(backup_dest), exist_ok=True)
        
        try:
            shutil.copy2(src_path, backup_dest)
            print(f"📦 Backed up: {rel_path}")
        
        except Exception as e:
            print(f"⚠️ Failed to back up {src_path}: {e}")
            continue

        # Compress to a lossy format
        if ATTEMPT_COMPRESSION:
            new_ext, codec = get_output_extension_and_codec(src_ext)
            rel_path_compressed = os.path.splitext(rel_path)[0] + new_ext
            compressed_dest = os.path.join(COMPRESSED_OUT_DIR, rel_path_compressed)
            os.makedirs(os.path.dirname(compressed_dest), exist_ok=True)

            ok = compress_with_ffmpeg(src_path, compressed_dest, TARGET_BITRATE, codec)
            
            if ok:
                new_size = os.path.getsize(compressed_dest) / (1024 * 1024)
                print(f"✅ Compressed: {rel_path} → {new_ext} ({new_size:.2f} MB)")
            else:
                print(f"⚠️ Compression failed for: {rel_path}")

    print("\n✔️ Backup and compression process complete.")


def save_log(results):
    '''This function will save the log after the processing is done'''
    with open(LOG_FILE, "w", encoding="utf-8") as log:
        log.write("Audio Compression Analysis Log\n")
        log.write(f"Scan Path: {INPUT_ROOT_DIR}\n")
        log.write(f"Tolerance: {TOLERANCE}\n")
        log.write(f"Target Bitrate: {TARGET_BITRATE}\n")
        log.write(f"Generated: {datetime.datetime.now()}\n")
        log.write("=" * 100 + "\n\n")

        for r in results:
            if LOG_ONLY_FLAGGED and not r["needs_compression"]:
                continue
            log.write(f"File: {r['file']}\n")
            log.write(f"Duration (s): {r['duration_sec']}\n")
            log.write(f"Bitrate (kbps): {r['bitrate_kbps']}\n")
            log.write(f"Actual Size (MB): {r['actual_size_mb']}\n")
            log.write(f"Expected Size (MB): {r['expected_size_mb']}\n")
            log.write(f"Needs Compression: {'YES' if r['needs_compression'] else 'NO'}\n")
            log.write("-" * 60 + "\n")

        flagged = [r for r in results if r["needs_compression"]]
        log.write("\nSummary:\n")
        log.write(f"Total files analyzed: {len(results)}\n")
        log.write(f"Files flagged for compression: {len(flagged)}\n")

    print(f"\n📘 Log saved to: {LOG_FILE}")
    print(f"Files flagged for compression: {len([r for r in results if r['needs_compression']])}")


def main():
    print(f"Scanning {INPUT_ROOT_DIR} for audio files...\n")
    results = scan_directory(INPUT_ROOT_DIR)
    save_log(results)
    handle_flagged_files(results)


if __name__ == "__main__":
    main()
