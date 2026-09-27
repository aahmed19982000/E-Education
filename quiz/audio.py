"""Server-side compression for quiz audio clips.

Every upload is re-encoded to a small mono MP3: 48 kbps is plenty for clear
speech, and MP3 plays on every browser (unlike Opus on older iPhones). A
one-minute clip ends up around 350 KB whatever format it was uploaded in.
"""
import logging
import os
import shutil
import subprocess
import tempfile

from django.core.files.base import ContentFile

logger = logging.getLogger(__name__)

BITRATE = "48k"
SAMPLE_RATE = "24000"
TIMEOUT_SECONDS = 120


class AudioDecodeError(Exception):
    """ffmpeg could not read the file, so it isn't usable audio."""


def ffmpeg_path():
    """System ffmpeg if installed, otherwise the binary bundled with imageio-ffmpeg."""
    path = shutil.which("ffmpeg")
    if path:
        return path
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:  # package missing or no binary for this platform
        return None


def compress_audio(uploaded):
    """Return a ContentFile holding `uploaded` as a compressed MP3.

    If ffmpeg isn't available, the original upload is returned unchanged (and
    a warning logged) so saving a question never breaks because of it. If the
    compressed version would somehow be bigger, the original is kept as well.
    """
    ffmpeg = ffmpeg_path()
    if not ffmpeg:
        logger.warning("ffmpeg not found; storing quiz audio without compression.")
        return uploaded

    base = os.path.splitext(os.path.basename(uploaded.name))[0] or "audio"
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "input")
        dst = os.path.join(tmp, "output.mp3")
        with open(src, "wb") as fh:
            for chunk in uploaded.chunks():
                fh.write(chunk)

        cmd = [
            ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y",
            "-i", src,
            "-vn", "-map_metadata", "-1",       # drop cover art and tags
            "-ac", "1", "-ar", SAMPLE_RATE,     # mono, speech-friendly sample rate
            "-c:a", "libmp3lame", "-b:a", BITRATE,
            dst,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=TIMEOUT_SECONDS)
        except subprocess.CalledProcessError as exc:
            logger.info("ffmpeg rejected quiz audio %s: %s", uploaded.name, exc.stderr.decode(errors="ignore")[-500:])
            raise AudioDecodeError(uploaded.name) from exc
        except subprocess.TimeoutExpired:
            logger.warning("ffmpeg timed out compressing %s; storing original.", uploaded.name)
            uploaded.seek(0)
            return uploaded

        with open(dst, "rb") as fh:
            data = fh.read()

    if not data:
        raise AudioDecodeError(uploaded.name)
    if uploaded.size and len(data) >= uploaded.size:
        uploaded.seek(0)
        return uploaded
    return ContentFile(data, name=f"{base}.mp3")
