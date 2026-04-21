# VideoTranscribe

Small Python script that:

- receives either a local video file path, a direct video URL, or a YouTube URL,
- extracts the audio with `ffmpeg`,
- transcribes the audio with OpenAI Whisper,
- writes the transcript to a `.txt` file next to the video.

## What It Does

The script supports three input types:

- local video files such as `/path/to/video.mp4`
- direct downloadable video URLs such as `https://example.com/video.mp4`
- YouTube URLs such as `https://www.youtube.com/watch?v=...`

For remote URL inputs, the script downloads the video into `assets/` first and then processes it exactly like a local file.

Current features:

- Whisper model selection with `--model`
- readable paragraph-based transcript formatting
- download progress for remote files
- extraction progress with `ffmpeg`
- elapsed time reporting for extraction, transcription, and total runtime
- optional cleanup of downloaded URL videos with `--delete-download`
- fully local transcription with no external transcription API

## Requirements

- Python 3
- `pip`
- `ffmpeg` installed and available in your `PATH`
- `ffprobe` available in your `PATH` (it is usually installed together with `ffmpeg`)

Python dependencies are managed with `requirements.txt`:

```txt
openai-whisper==20250625
yt-dlp==2026.3.17
```

Whisper models are downloaded on first use and cached locally. Approximate
model sizes:

| Model | Download size |
| --- | --- |
| `small` | ~460 MB |
| `medium` | ~1.5 GB |
| `large` | ~2.9 GB |

By default, Whisper stores models in `~/.cache/whisper` on macOS and Linux.
On Windows, the cache is typically under the current user's local application
data directory.

## Local Setup

### 1. Get the project

Clone the repository or copy the project folder to your machine.

### 2. Create a virtual environment

From the project root:

```bash
python3 -m venv .venv
```

### 3. Activate the virtual environment

macOS / Linux:

```bash
source .venv/bin/activate
```

Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

### 4. Install Python dependencies

```bash
pip install -r requirements.txt
```

### 5. Install ffmpeg

This project depends on `ffmpeg` to extract audio from video files.

macOS with Homebrew:

```bash
brew install ffmpeg
```

Ubuntu / Debian:

```bash
sudo apt update
sudo apt install ffmpeg
```

Windows:

Install FFmpeg using `winget`:

```powershell
winget install Gyan.FFmpeg
```

After installation, open a new terminal so the updated `PATH` is picked up.

### 6. Verify the setup

Check that Python dependencies are installed:

```bash
python -c "import whisper; print('whisper ok')"
```

Check that `ffmpeg` is available:

```bash
ffmpeg -version
```

Optional: check that `ffprobe` is available too:

```bash
ffprobe -version
```

For later sessions, you usually only need to reactivate the environment:

```bash
source .venv/bin/activate
```

## Quick Start

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python v2t.py /path/to/video.mp4
```

## Usage

Run the script with a local video file path:

```bash
python v2t.py /path/to/video.mp4
```

Example:

```bash
python v2t.py ~/Downloads/video.mp4
```

Select a Whisper model with `--model`:

```bash
python v2t.py --model medium ~/Downloads/video.mp4
```

You can also pass a direct video URL:

```bash
python v2t.py "https://example.com/video.mp4"
```

For URL inputs, the script downloads the file into the `assets/` folder first and then runs the same extraction and transcription flow.

The transcript is always written next to the video file being processed.

- local file input: transcript is created next to that local file
- remote URL input: the video is first downloaded into `assets/`, so the transcript is also created in `assets/`

You can also pass a YouTube URL with no extra flags:

```bash
python v2t.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

The script detects YouTube URLs automatically and downloads them with `yt-dlp` before transcription.

Delete the downloaded remote file after a successful run:

```bash
python v2t.py --delete-download "https://example.com/video.mp4"
```

Combine options:

```bash
python v2t.py --model large --delete-download "https://example.com/video.mp4"
```

CLI help:

```bash
python v2t.py --help
```

## How Input Is Handled

- If the URL host is a supported YouTube host such as `youtube.com` or `youtu.be`, it is treated as a YouTube URL and downloaded with `yt-dlp`.
- Other `http://` and `https://` URLs are treated as direct downloadable video files.
- Otherwise, it is treated as a local file path.
- Local files are used directly.
- Remote URL inputs are downloaded into `assets/` and then passed through the same extraction and transcription pipeline.
- If a downloaded filename already exists, the script creates a unique name instead of overwriting the existing file.

## Output

The transcript is always created in the same directory as the video file being processed.

- local file input: if the video is `/path/to/movie.mp4`, the transcript will be `/path/to/movie_transcript.txt`
- remote URL input: the video is first downloaded into `assets/`, so both the downloaded video and the transcript are created in `assets/`

The output is formatted into readable paragraphs instead of a single text block.

During execution, the script shows:

- download progress for remote URL inputs,
- extraction progress from `ffmpeg`,
- a transcription start/completion message from Whisper,
- elapsed time for extraction, transcription, and total runtime.

Examples:

- input: `movie.mp4`
- output: `movie_transcript.txt`
- input: `assets/lecture.mp4`
- output: `assets/lecture_transcript.txt`

## Notes

- The first transcription may take longer because Whisper may download the selected model.
- The default Whisper model is `small`.
- Allowed model values are `small`, `medium`, and `large`.
- Whisper runs locally on your machine. No transcript is sent to an external API.
- YouTube URLs are supported automatically.
- Non-YouTube remote URLs must point directly to downloadable video files over `http` or `https`.
- Other video platform page URLs such as Vimeo are not supported.
- Downloaded URL videos are kept by default.
- Use `--delete-download` if you want the downloaded video removed after a successful transcription.
- `ffmpeg` is a system dependency and is not installed through `requirements.txt`.

## License

This project is released under the MIT License. See `LICENSE` for details.

## Troubleshooting

If you get `ModuleNotFoundError: No module named 'whisper'`:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

If `python` is not using the virtual environment, check:

```bash
which python
```

It should point to `.venv/bin/python`.

If `ffmpeg` is missing, install it first and retry the command.

If `ffprobe` is missing, install `ffmpeg` again and ensure its tools are available in your `PATH`.

If a non-YouTube URL does not download correctly, make sure it points directly to a video file and not to a generic web page.

If a YouTube URL fails, make sure `yt-dlp` is installed from `requirements.txt` and try again.

If transcription seems slow, try a smaller model:

```bash
python v2t.py --model small /path/to/video.mp4
```
