import argparse
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request

try:
    import whisper
except ModuleNotFoundError:
    print(
        "Missing dependency: openai-whisper. "
        "Activate your virtual environment and run 'pip install -r requirements.txt'."
    )
    sys.exit(1)


PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(PROJECT_DIR, "assets")
MODEL_CHOICES = ["tiny", "base", "small", "medium", "large"]
YOUTUBE_HOSTS = {
    "youtube.com",
    "www.youtube.com",
    "m.youtube.com",
    "youtu.be",
    "www.youtu.be",
}


def format_transcript(result, max_paragraph_chars=500):
    segments = result.get("segments") or []
    if not segments:
        return result.get("text", "").strip()

    paragraphs = []
    current_parts = []
    current_length = 0

    for segment in segments:
        text = segment.get("text", "").strip()
        if not text:
            continue

        current_parts.append(text)
        current_length += len(text) + 1

        if current_length >= max_paragraph_chars and text[-1] in ".!?":
            paragraphs.append(" ".join(current_parts))
            current_parts = []
            current_length = 0

    if current_parts:
        paragraphs.append(" ".join(current_parts))

    return "\n\n".join(paragraphs)


def format_timestamp(seconds, decimal_marker):
    total_milliseconds = max(0, int(round(seconds * 1000)))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, milliseconds = divmod(remainder, 1000)
    return (
        f"{hours:02d}:{minutes:02d}:{secs:02d}{decimal_marker}{milliseconds:03d}"
    )


def format_subtitles(result, output_format):
    segments = result.get("segments") or []
    if not segments:
        raise RuntimeError(
            "Whisper did not return timestamped segments, so subtitle output could "
            "not be generated."
        )

    blocks = []
    cue_number = 1
    decimal_marker = "," if output_format == "srt" else "."

    for segment in segments:
        text = segment.get("text", "").strip()
        if not text:
            continue

        start = max(0.0, float(segment.get("start", 0.0)))
        end = max(start, float(segment.get("end", start)))
        timestamp_line = (
            f"{format_timestamp(start, decimal_marker)} --> "
            f"{format_timestamp(end, decimal_marker)}"
        )

        if output_format == "srt":
            blocks.append(f"{cue_number}\n{timestamp_line}\n{text}")
            cue_number += 1
        else:
            blocks.append(f"{timestamp_line}\n{text}")

    if output_format == "vtt":
        return "WEBVTT\n\n" + "\n\n".join(blocks) + "\n"

    return "\n\n".join(blocks) + "\n"


def format_duration(seconds):
    total_seconds = max(0, int(round(seconds)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_size(num_bytes):
    units = ["B", "KB", "MB", "GB"]
    size = float(num_bytes)
    unit = units[0]
    for unit in units:
        if size < 1024 or unit == units[-1]:
            break
        size /= 1024

    if unit == "B":
        return f"{int(size)} {unit}"
    return f"{size:.1f} {unit}"


def get_media_duration(video_path):
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        video_path,
    ]
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None


def print_progress(label, processed_seconds, total_seconds=None):
    if total_seconds and total_seconds > 0:
        percent = min(100.0, processed_seconds / total_seconds * 100)
        message = (
            f"\r{label}: {percent:5.1f}% "
            f"({format_duration(processed_seconds)} / {format_duration(total_seconds)})"
        )
    else:
        message = f"\r{label}: {format_duration(processed_seconds)}"

    print(message, end="", flush=True)


def print_download_progress(label, downloaded_bytes, total_bytes=None):
    if total_bytes and total_bytes > 0:
        percent = min(100.0, downloaded_bytes / total_bytes * 100)
        message = (
            f"\r{label}: {percent:5.1f}% "
            f"({format_size(downloaded_bytes)} / {format_size(total_bytes)})"
        )
    else:
        message = f"\r{label}: {format_size(downloaded_bytes)}"

    print(message, end="", flush=True)


def is_url(value):
    parsed = urllib.parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def is_youtube_url(value):
    parsed = urllib.parse.urlparse(value)
    hostname = (parsed.hostname or "").lower()
    return hostname in YOUTUBE_HOSTS


def ensure_assets_dir():
    os.makedirs(ASSETS_DIR, exist_ok=True)


def get_unique_path(path):
    if not os.path.exists(path):
        return path

    base, ext = os.path.splitext(path)
    counter = 1
    while True:
        candidate = f"{base}_{counter}{ext}"
        if not os.path.exists(candidate):
            return candidate
        counter += 1


def get_download_filename(url, response):
    header_filename = response.headers.get_filename()
    if header_filename:
        filename = header_filename
    else:
        parsed = urllib.parse.urlparse(url)
        filename = os.path.basename(urllib.parse.unquote(parsed.path))

    if not filename:
        filename = "downloaded_video.mp4"

    return os.path.basename(filename)


def get_output_path(video_path, output_format, output_dir=None):
    if output_dir:
        output_directory = output_dir
        os.makedirs(output_directory, exist_ok=True)
    else:
        output_directory = os.path.dirname(video_path) or "."

    video_name = os.path.splitext(os.path.basename(video_path))[0]
    return os.path.join(output_directory, f"{video_name}_transcript.{output_format}")


def download_video(url):
    ensure_assets_dir()
    print(f"Downloading video from URL: {url}")

    started_at = time.perf_counter()
    with urllib.request.urlopen(url) as response:
        filename = get_download_filename(url, response)
        output_path = get_unique_path(os.path.join(ASSETS_DIR, filename))
        total_bytes = response.headers.get("Content-Length")
        total_bytes = int(total_bytes) if total_bytes else None

        downloaded_bytes = 0
        with open(output_path, "wb") as output_file:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                output_file.write(chunk)
                downloaded_bytes += len(chunk)
                print_download_progress("Downloading video", downloaded_bytes, total_bytes)

    print()
    elapsed = time.perf_counter() - started_at
    print(f"Video downloaded to: {output_path}")
    print(f"Download completed in {format_duration(elapsed)}")
    return output_path


def download_youtube_video(url):
    ensure_assets_dir()

    try:
        import yt_dlp
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            "Missing dependency: yt-dlp. Activate your virtual environment and run "
            "'pip install -r requirements.txt'."
        ) from e

    print(f"Downloading YouTube video: {url}")

    started_at = time.perf_counter()
    downloaded_path = None

    def progress_hook(status):
        nonlocal downloaded_path

        if status.get("status") == "downloading":
            percent_text = status.get("_percent_str", "").strip()
            downloaded_bytes = status.get("downloaded_bytes")
            total_bytes = status.get("total_bytes") or status.get("total_bytes_estimate")

            if downloaded_bytes is not None:
                if total_bytes:
                    print_download_progress(
                        "Downloading video",
                        downloaded_bytes,
                        total_bytes,
                    )
                else:
                    message = f"\rDownloading video: {percent_text or format_size(downloaded_bytes)}"
                    print(message, end="", flush=True)
        elif status.get("status") == "finished":
            filename = status.get("filename")
            if filename:
                downloaded_path = filename

    def postprocessor_hook(status):
        nonlocal downloaded_path

        if status.get("status") == "finished":
            filepath = status.get("info_dict", {}).get("filepath")
            if filepath:
                downloaded_path = filepath

    options = {
        "outtmpl": os.path.join(ASSETS_DIR, "%(title)s.%(ext)s"),
        "restrictfilenames": False,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        "progress_hooks": [progress_hook],
        "postprocessor_hooks": [postprocessor_hook],
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            info = ydl.extract_info(url, download=True)
            if not downloaded_path:
                downloaded_path = info.get("filepath") or ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError as e:
        raise RuntimeError(f"Error downloading YouTube video: {e}") from e

    print()
    elapsed = time.perf_counter() - started_at
    print(f"Video downloaded to: {downloaded_path}")
    print(f"Download completed in {format_duration(elapsed)}")
    return downloaded_path


def resolve_video_path(input_value):
    if is_youtube_url(input_value):
        return download_youtube_video(input_value), True

    if is_url(input_value):
        return download_video(input_value), True

    if not os.path.exists(input_value):
        raise FileNotFoundError(f"File '{input_value}' not found.")

    return input_value, False


def extract_audio(video_path, audio_path):
    total_duration = get_media_duration(video_path)
    command = [
        "ffmpeg",
        "-i",
        video_path,
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "44100",
        "-ac",
        "2",
        audio_path,
        "-y",
        "-progress",
        "pipe:1",
        "-nostats",
    ]

    started_at = time.perf_counter()
    process = subprocess.Popen(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    processed_seconds = 0.0
    for line in process.stdout:
        line = line.strip()
        if line.startswith("out_time_us=") or line.startswith("out_time_ms="):
            _, value = line.split("=", 1)
            try:
                processed_seconds = float(value) / 1_000_000
            except ValueError:
                continue
            print_progress("Extracting audio", processed_seconds, total_duration)

    stderr_output = process.stderr.read()
    return_code = process.wait()
    print()

    if return_code != 0:
        raise subprocess.CalledProcessError(return_code, command, stderr=stderr_output)

    return time.perf_counter() - started_at


def transcribe_video(
    video_path,
    model_name,
    language=None,
    output_format="txt",
    output_dir=None,
    total_started_at=None,
):
    fd, audio_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)
    if total_started_at is None:
        total_started_at = time.perf_counter()

    try:
        # 1. Extract audio using ffmpeg
        extraction_elapsed = extract_audio(video_path, audio_path)
        print(f"Audio extracted in {format_duration(extraction_elapsed)}")

        # 2. Transcribe using Whisper
        print(f"Loading Whisper model '{model_name}' (this may take a moment)...")
        model = whisper.load_model(model_name)

        print("Transcribing...")
        transcribe_options = {"verbose": False}
        if language:
            transcribe_options["language"] = language
        if str(model.device) == "cpu":
            transcribe_options["fp16"] = False

        transcription_started_at = time.perf_counter()
        result = model.transcribe(audio_path, **transcribe_options)
        transcription_elapsed = time.perf_counter() - transcription_started_at
        print(f"Transcription completed in {format_duration(transcription_elapsed)}")

        # 3. Save to file
        output_file = get_output_path(video_path, output_format, output_dir)
        if output_format == "txt":
            output_text = format_transcript(result)
        else:
            output_text = format_subtitles(result, output_format)

        with open(output_file, "w", encoding="utf-8") as f:
            f.write(output_text)

        total_elapsed = time.perf_counter() - total_started_at
        print(f"Transcription saved to: {output_file}")
        print(f"Total time: {format_duration(total_elapsed)}")
        return True

    except subprocess.CalledProcessError as e:
        print(f"Error during audio extraction: {e.stderr}")
        return False
    finally:
        # Cleanup
        if os.path.exists(audio_path):
            os.remove(audio_path)


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "VideoTranscribe extracts audio from a video file and transcribes it "
            "with Whisper."
        )
    )
    parser.add_argument(
        "video_path",
        help="Path to a local video file, direct video URL, or YouTube URL",
    )
    parser.add_argument(
        "--model",
        choices=MODEL_CHOICES,
        default="small",
        help="Whisper model to use (default: small)",
    )
    parser.add_argument(
        "--language",
        help="Optional language code for Whisper (default: auto-detect)",
    )
    parser.add_argument(
        "--output-format",
        choices=["txt", "srt", "vtt"],
        default="txt",
        help="Output format to write (default: txt)",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional directory for transcript output (default: next to the video)",
    )
    parser.add_argument(
        "--delete-download",
        action="store_true",
        help="Delete downloaded URL videos after transcription finishes",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    downloaded_video_path = None
    completed = False
    try:
        run_started_at = time.perf_counter()
        resolved_video_path, was_downloaded = resolve_video_path(args.video_path)
        if was_downloaded:
            downloaded_video_path = resolved_video_path
        completed = transcribe_video(
            resolved_video_path,
            args.model,
            language=args.language,
            output_format=args.output_format,
            output_dir=args.output_dir,
            total_started_at=run_started_at,
        )
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except urllib.error.URLError as e:
        print(f"Error downloading video: {e}")
    except ModuleNotFoundError as e:
        print(e)
    except RuntimeError as e:
        print(e)
    finally:
        if (
            completed
            and args.delete_download
            and downloaded_video_path
            and os.path.exists(downloaded_video_path)
        ):
            os.remove(downloaded_video_path)
            print(f"Deleted downloaded video: {downloaded_video_path}")
