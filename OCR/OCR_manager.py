
'''
OCR_Usage.py

Author: Trinh Pham

This script allows one to choose which OCR engine to use. 

OCR engine qualifications:
- Formatting
    - VIDEO
    - IMAGE
    - TEXT
- Quality of Transformation
    - SUMMARY
    - Accuracy of Processing

-> Google cloud for the video text processing

 
'''

try:
    from .OCR import c_OCR, c_GoogleCloudOCR, c_TesseractOCR, c_DeepSeekOCR
except ImportError:
    from OCR.OCR import c_OCR, c_GoogleCloudOCR, c_TesseractOCR, c_DeepSeekOCR

_CONSTRUCTOR_TOKEN = object()


# This class is a singleton, such that there is only one instance of it throughout the application.
class c_OCRManager:
    _instance = None                                    # Singleton instance of the class

    engine: c_OCR                                       # the currently active OCR engine object

    def __new__(cls, engine: c_OCR | None = None, _token: object = None):  # cls represents the class itself, used for creating a singleton instance
        if _token is not _CONSTRUCTOR_TOKEN:                    # Ensures that the constructor is only called through the f_get_instance method
            raise TypeError("Use c_OCRManager.f_get_instance() to access the OCR manager")
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, engine: c_OCR | None = None, _token: object = None) -> None:
        if _token is not _CONSTRUCTOR_TOKEN:
            raise TypeError("Use c_OCRManager.f_get_instance() to access the OCR manager")
        self.engine = engine or c_GoogleCloudOCR()      # defaults to Google Cloud OCR when none is provided
        self.deepSeek = c_DeepSeekOCR()                 # text post-processing is independent of the active video/image OCR engine

    @classmethod
    def f_get_instance(cls, engine: c_OCR | None = None):
        return cls(engine, _CONSTRUCTOR_TOKEN)          # Returns the singleton instance of the class

    def f_switch_engine(self, engine: c_OCR) -> None:
        self.engine = engine

    def f_assign_engine(self, engine: c_OCR) -> None:
        self.engine = engine

    def f_connect_engine(self) -> str:
        # Placeholder for actual OCR engine connection logic
        return f"Connected to {self.engine.f_get_engine()} OCR engine"

    def f_upload_file(self, file_path: str) -> str:   # uploads only, ahead of running OCR/text detection
        return self.engine.f_upload_video(file_path)

    def f_organize_text(self, acRawText: str) -> str:   # runs just the text-organization step, e.g. on text from a prior run
        return self.engine.f_organize_text(acRawText)

    def f_split_dialogue_words(self, acOrganizedText: str) -> str:   # further splits every sentence in the DIALOGUE section into its individual words
        return self.deepSeek.f_split_dialogue_words(acOrganizedText)

    def f_process_file(self, file_path: str) -> str:
        return self.engine.f_perform_ocr(file_path)

class c_OCRFactory:
    @staticmethod
    def f_create_engine(engine: str) -> c_OCR:
        if engine.lower() == "googlecloud":
            return c_GoogleCloudOCR()
        elif engine.lower() == "tesseract":
            return c_TesseractOCR()
        elif engine.lower() == "deepseek":
            return c_DeepSeekOCR()
        else:
            raise ValueError("Unsupported OCR engine")
    