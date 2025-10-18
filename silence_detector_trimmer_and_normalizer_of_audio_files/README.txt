SCRIPT: detect_log_silence.py 
Can be used for silence detection and logging of audio files which contain silent segments.

SCRIPT: detect_log_and_trim_silence
Can be used for a more enhanced and accurate silence detection, silence trimming, and volume normalization of 
audio files which contain silent segments.


THESE PYTHON SCRIPTS REQUIRES FFMPEG LIBRARY

IT WAS TESTED WITH ffmpeg8.0-essentials_build


Visit the FFmpeg download page. The More downloading options section has FFmpeg packages and executable files for Linux, Windows, 
and Mac.

Extract the Downloaded Files

Rename the extracted folder to ffmpeg.

Move the folder to the root of the C drive or the folder of your choice.

Add FFmpeg to PATH (environment variables)

Set Windows environment variables to add FFmpeg to the PATH.

----------------------------------------------
You can use ffmpeg without the environment variable by altering the scripts using
the dynamic filepath to the ffmpeg.exe instead of simply typing the ffmpeg command.

EXAMPLE - EDIT IN THE SCRIPT:
ffmpeg

WITH

"C:\Program Files\ffmpeg\bin\ffmpeg.exe"

supposing the ffmpeg directory is placed in C:\Program Files\

----------------------------------------------

To add the environment variable:

Type system variables into the search bar and click the Edit the system environment variables option.

Click the Environment Variables... button under the Advanced tab..

Under the User variables section, select Path and click the Edit button.

Choose New from the side menu.

Add C:\ffmpeg\bin to the empty field and confirm changes with OK.

Verify FFmpeg PATH - open the Command Prompt and type: 
ffmpeg -version
