

'''
OCR.py

Author: Trinh Pham

This script contains the core OCR functionality.
'''

import mimetypes                # for guessing the content type when uploading via a wrapped file object
import os                       # for reading the GCS bucket name from the environment
import re                       # for parsing MB/s rates out of past log entries
import sys                      # for checking whether stdout is a real terminal before emitting color codes
import time                     # for tracking elapsed processing time
from pathlib import Path        # for deriving a default blob name from the local file path
from typing import Callable

from dotenv import load_dotenv
from google.cloud import storage
from google.cloud import videointelligence
from openai import OpenAI   # DeepSeek's API is OpenAI-compatible

load_dotenv()   # loads .env into the environment before the class-level os.environ.get() calls below run


def f_green(acText: str) -> str:   # only colors output for real terminals, so redirected/log output stays plain
    if not sys.stdout.isatty():
        return acText
    return f"\033[32m{acText}\033[0m"


def f_bright_green(acText: str) -> str:   # used to highlight "done" messages
    if not sys.stdout.isatty():
        return acText
    return f"\033[92m{acText}\033[0m"


class c_UploadProgressFile:  # wraps a binary file so chunked GCS uploads can report byte-level progress as they read
    def __init__(self, file_path: str, on_read: Callable[[int], None]) -> None:
        self._pFile = open(file_path, "rb")
        self._on_read = on_read

    def read(self, size: int = -1) -> bytes:
        pChunk = self._pFile.read(size)
        self._on_read(len(pChunk))
        return pChunk

    def __getattr__(self, acName):
        return getattr(self._pFile, acName)

    def close(self) -> None:
        self._pFile.close()



class c_OCR:
    def __init__(self, engine: str = "Google Cloud") -> None:
        self.engine = engine

    def f_set_engine(self, engine: str) -> None:
        self.engine = engine

    def f_get_engine(self) -> str:
        return self.engine

    def f_upload_video(self, file_path: str) -> str:   # engines without remote storage just operate on the local path
        return file_path

    def f_organize_text(self, acRawText: str) -> str:   # engines without a text-organization step return the raw text unchanged
        return acRawText

    def f_perform_ocr(self, file_path: str) -> str:
        # Placeholder for actual OCR logic
        return f"Performed OCR on {file_path} using {self.engine} engine"

class c_GoogleCloudOCR(c_OCR):
    # Overridable via the GCS_BUCKET_NAME environment variable
    acBucketName = "cloud_bucket_test_for_ocr"
    BUCKET_NAME = os.environ.get("GCS_BUCKET_NAME", acBucketName)
    # ADC from `gcloud auth application-default login` has no project embedded, so it must be supplied explicitly
    PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT", "project-0059f1a7-e9ee-4aca-83a")
    # Set via the DEEPSEEK_API_KEY environment variable to enable text organization; get a key at platform.deepseek.com
    DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
    DEEPSEEK_MODEL = "deepseek-chat"

    calculationTime: float = 0.0   # tracks the total time spent in f_detect_text() for all videos processed by this instance

    # Reference point for estimating TEXT_DETECTION processing time (Video Intelligence's own progress_percent is unreliable):
    # GameTest1.MP4 (275,469,829 bytes) took ~10 minutes, so other videos are scaled by their byte size relative to this one
    REFERENCE_VIDEO_BYTES = 275_469_829
    REFERENCE_PROCESSING_SECONDS = 10 * 60

    def __init__(self) -> None:
        super().__init__(engine="Google Cloud")

    def f_upload_video(self, file_path: str, acBlobName: str | None = None) -> str:  # uploads a local video to GCS ahead of any processing, returns its gs:// URI
        if not self.BUCKET_NAME:
            raise ValueError("GCS_BUCKET_NAME environment variable is not set")

        pClient = storage.Client(project=self.PROJECT_ID)
        pBucket = pClient.bucket(self.BUCKET_NAME)
        acBlobName = acBlobName or Path(file_path).name
        pBlob = pBucket.blob(acBlobName)
        pBlob.chunk_size = 8 * 1024 * 1024   # upload in 8 MB chunks so progress can be reported between chunks

        iTotalBytes = Path(file_path).stat().st_size
        fStartTime = time.time()
        iBytesRead = 0
        fLastPrintTime = 0.0

        def f_on_read(iChunkSize: int) -> None:
            nonlocal iBytesRead, fLastPrintTime
            iBytesRead += iChunkSize
            fNow = time.time()
            if fNow - fLastPrintTime < 0.2 and iBytesRead < iTotalBytes:   # cap updates to ~5/sec so the line doesn't spam
                return
            fLastPrintTime = fNow
            fPercent = (iBytesRead / iTotalBytes * 100) if iTotalBytes else 0.0
            print(f_green(f"\rUploading video... {fPercent:5.1f}% ({int(fNow - fStartTime)}s elapsed)"), end="", flush=True)

        pProgressFile = c_UploadProgressFile(file_path, f_on_read)
        try:
            pBlob.upload_from_file(pProgressFile, size=iTotalBytes, content_type=mimetypes.guess_type(file_path)[0])
        finally:
            pProgressFile.close()
        print(f_bright_green(f"\rUploading video... 100.0% (done in {int(time.time() - fStartTime)}s)") + " " * 10)

        return f"gs://{self.BUCKET_NAME}/{acBlobName}"

    def f_average_rate_MBps(self) -> float | None:   # averages the MB/s rate across past logged runs, so estimates reflect real observed throughput instead of a fixed guess
        pLogFile = Path(__file__).parent.parent / "Logs" / "ocr_log.txt"
        if not pLogFile.exists():
            return None

        aRates = [float(acRate) for acRate in re.findall(r"rate=([\d.]+) MB/s", pLogFile.read_text(encoding="utf-8"))]
        return sum(aRates) / len(aRates) if aRates else None

    def f_detect_text(self, acGcsUri: str, iVideoBytes: int | None = None) -> str:  # runs Video Intelligence text detection on an already-uploaded video and returns the recognized text
        pClient = videointelligence.VideoIntelligenceServiceClient()
        pOperation = pClient.annotate_video(
            request={
                "features": [videointelligence.Feature.TEXT_DETECTION],
                "input_uri": acGcsUri,
            }
        )

        fEstimatedTotalSeconds = None
        if iVideoBytes:
            fAverageRateMBps = self.f_average_rate_MBps()
            if fAverageRateMBps:   # prefer real observed throughput from past runs
                fEstimatedTotalSeconds = (iVideoBytes / (1024 * 1024)) / fAverageRateMBps
            else:   # no log history yet, so fall back to the GameTest1 reference estimate
                fEstimatedTotalSeconds = (iVideoBytes / self.REFERENCE_VIDEO_BYTES) * self.REFERENCE_PROCESSING_SECONDS

        fStartTime = time.time()
        fNextPollTime = 0.0
        POLL_INTERVAL_SECONDS = 5   # stay well under the API's 60 requests/minute quota for GetOperation polls
        acEstimateSuffix = f" (expected minutes: {fEstimatedTotalSeconds / 60:.1f})" if fEstimatedTotalSeconds else ""

        bDone = False
        while not bDone:   # progress_percent from the API is unreliable, so estimate from elapsed time vs. the video's duration instead
            fElapsed = time.time() - fStartTime
            fPercent = min(99.0, fElapsed / fEstimatedTotalSeconds * 100) if fEstimatedTotalSeconds else 0.0
            print(f_green(f"\rDetecting text... {fPercent:5.1f}% ({int(fElapsed)}s elapsed, {fElapsed / 60:.1f} min){acEstimateSuffix}"), end="", flush=True)

            if fElapsed >= fNextPollTime:   # only the .done() check hits the network; the print above is purely local
                bDone = pOperation.done()
                fNextPollTime = fElapsed + POLL_INTERVAL_SECONDS

            if not bDone:
                time.sleep(1)
        fTotalElapsed = time.time() - fStartTime
        print(f_bright_green(f"\rDetecting text... 100.0% (done in {int(fTotalElapsed)}s, {fTotalElapsed / 60:.1f} min){acEstimateSuffix}") + " " * 10)

        pResult = pOperation.result(timeout=600)
        if pResult is None:
            return ""

        aTimedLines = []
        for pTextAnnotation in pResult.annotation_results[0].text_annotations:
            # each annotation can appear in multiple frames; use its earliest occurrence so lines can be ordered/grouped by when they appeared
            fFirstSeenSeconds = min(
                (pSegment.segment.start_time_offset.total_seconds() for pSegment in pTextAnnotation.segments),
                default=0.0,
            )
            aTimedLines.append((fFirstSeenSeconds, pTextAnnotation.text))

        aTimedLines.sort(key=lambda pEntry: pEntry[0])   # chronological order lets nearby name-plate/dialogue lines be grouped by DeepSeek
        return "\n".join(f"[{fSeconds:7.1f}s] {acText}" for fSeconds, acText in aTimedLines)

    def f_organize_text(self, acRawText: str) -> str:  # asks DeepSeek to dedupe/reorder the raw per-frame OCR text into readable output
        if not acRawText.strip():
            return acRawText
        if not self.DEEPSEEK_API_KEY:
            print("DEEPSEEK_API_KEY not set; skipping text organization step")
            return acRawText

        try:
            pClient = OpenAI(api_key=self.DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            pResponse = pClient.chat.completions.create(
                model=self.DEEPSEEK_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "1.You clean up raw text detected across video frames by an OCR system. "
                            "Each line is prefixed with a '[123.4s]' timestamp marking when it first appeared on screen. "
                            "2.Remove duplicate/near-duplicate lines from repeated frames, merge fragmented "
                            "words, and organize the remaining text in chronological (timestamp) order within each section below. "
                            "3.Keep all text in its original language; do not translate or summarize anything. "
                            "4.Lines that appear within a couple seconds of each other are likely from the same on-screen "
                            "moment. Where a dialogue line can be confidently matched to a nearby speaker name label based "
                            "on this timing, prefix that line with the speaker's name (e.g. 'Name: dialogue') and drop the "
                            "timestamp from the final output. If a line's speaker is unclear, leave it unattributed "
                            "rather than guessing. Do not invent any new content."
                            "5.If a LINE of text is purely Non-Japanese and does not contain any English nor Japanese character other than special symbols,"
                            " remove it from the output."
                            "6.Split the final output into exactly three labeled sections, in this order: "
                            "'=== DIALOGUE ===' (actual character dialogue/story lines, attributed to speakers per rule 4); "
                            "'=== GAMEPLAY ===' (menus, buttons, actions, damage/skill numbers, stat bars, battle prompts, and similar UI/HUD text); "
                            "'=== MISC ===' (anything else, including system notifications and text that doesn't clearly belong in the other two, "
                            "such as the non-related Japanese text from rule 5)."
                            "7. Make it so that the dialogue is categorized into scenes if there are any scenes that can be identified. If there are no scenes, then just categorize the dialogue into a single scene."
                            "8. Make sure that the gameplay section only has text that is either completely or fully in Japanese. For example, "
                            "< CHAPTER 3 避けられない犠牲 >. Include that and such. Exclude things like these: 'Do Not', "
                            "'Not Playing', 'Disturb', 'EPISODE'. Also exclude things that are only just numbers with no Japanese characters. " 
                        ),
                    },
                    {"role": "user", "content": f"Go ahead and sort this out into the three sections described. Here is the text: \n{acRawText}"},
                ],
                max_tokens=10000,   # caps the cost of a single call regardless of input size
            )
            acChoice = pResponse.choices[0]
            if not acChoice.message.content:   # empty/None content isn't an exception, so it needs its own diagnostic
                print(f"DeepSeek returned no content (finish_reason={acChoice.finish_reason}, usage={pResponse.usage}); returning raw text")
                return acRawText
            if acChoice.finish_reason == "length":   # organized output got cut off mid-way by max_tokens
                print(f"DeepSeek output was truncated by max_tokens (usage={pResponse.usage})")
            return acChoice.message.content
        except Exception as e:
            print(f"DeepSeek text organization failed, returning raw text: {e!r}")
            return acRawText

    def f_log_metrics(self, file_path: str, iVideoBytes: int, fElapsedSeconds: float) -> None:   # appends one line per fully-processed file: time, byte size, and MB/sec rate
        pLogDir = Path(__file__).parent.parent / "Logs"
        pLogDir.mkdir(parents=True, exist_ok=True)
        fMegabytesPerSecond = (iVideoBytes / (1024 * 1024)) / fElapsedSeconds if fElapsedSeconds else 0.0
        acLine = (
            f"{time.strftime('%Y-%m-%d %H:%M:%S')} | file={Path(file_path).name} | "
            f"time={fElapsedSeconds:.1f}s | bytes={iVideoBytes} | rate={fMegabytesPerSecond:.2f} MB/s\n"
        )
        with open(pLogDir / "ocr_log.txt", "a", encoding="utf-8") as pLogFile:
            pLogFile.write(acLine)

    def f_perform_ocr(self, file_path: str) -> str:
        fStartTime = time.time()
        acGcsUri = self.f_upload_video(file_path)
        iVideoBytes = Path(file_path).stat().st_size
        acDetectedText = self.f_detect_text(acGcsUri, iVideoBytes)
        self.f_log_metrics(file_path, iVideoBytes, time.time() - fStartTime)
        return acDetectedText

class c_TesseractOCR(c_OCR):
    def __init__(self) -> None:
        super().__init__(engine="Tesseract")

    def f_perform_ocr(self, file_path: str) -> str:
        # Placeholder for Tesseract OCR logic
        return f"Performed OCR on {file_path} using Tesseract OCR engine"
    