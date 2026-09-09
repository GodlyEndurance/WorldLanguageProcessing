
'''
mainHelper.py

Author: Trinh Pham

This file contains helper functions for the main executable script.

'''

from pathlib import Path

from OCR.OCR_manager import c_OCRFactory, c_OCRManager

try:
    from .DB.DBManager import c_DBManager
    from .DB.Data import c_Data, c_ImageData, c_TextData, c_VideoData
except ImportError:
    from DB.DBManager import c_DBManager
    from DB.Data import c_Data, c_ImageData, c_TextData, c_VideoData


# A support facade pattern for the main executable script
class c_MainHelper:
    def __init__(self, dbManager: c_DBManager | None = None, oCRM: c_OCRManager | None = None, test: bool = False, deleteAll: bool = False) -> None:
        self.dbManager = dbManager          # uses the provided DB manager for this class's database operations
        self.oCRM = oCRM
        self.test = test
        self.deleteAll = deleteAll

        if deleteAll:
            if self.dbManager is None:
                raise ValueError("A DB manager is required when deleteAll is True")
            self.dbManager.f_deleteDataAll()

    def f_rawDataPath(self, acFileName: str) -> Path:   # resolves input filenames against the Raw_Data folder
        return Path(__file__).parent / "Raw_Data" / acFileName

    def f_outputFilePath(self, acFileName: str) -> Path:   # resolves generated/output filenames against the "output files" folder
        return Path(__file__).parent / "output files" / acFileName

    def f_assignOCR(self, engine: str) -> None:
        if self.oCRM is None:
            raise ValueError("An OCR manager is required for OCR operations")
        self.oCRM.f_assign_engine(c_OCRFactory.f_create_engine(engine))

    def f_uploadFileOCR(self, acFileName: str) -> str:      # uploads the file to the OCR engine's storage (if applicable) and returns the remote path or URL
        if self.oCRM is None:
            raise ValueError("An OCR manager is required for OCR operations")
        fpFilePath = self.f_rawDataPath(acFileName)
        return self.oCRM.f_upload_file(str(fpFilePath))

    def f_processFileOCR(self, acFileName: str) -> str:     # runs the OCR engine on the file and returns the detected text
        if self.oCRM is None:
            raise ValueError("An OCR manager is required for OCR operations")
        print("Importing and processing the video file...")
        fpFilePath = self.f_rawDataPath(acFileName)
        return self.oCRM.f_process_file(str(fpFilePath))

    def f_organizeTextOCR(self, acRawText: str) -> str:   # runs just the text-organization step on already-detected text
        if self.oCRM is None:
            raise ValueError("An OCR manager is required for OCR operations")
        return self.oCRM.f_organize_text(acRawText)


    # PUBLIC INTERFACE FOR THE USER
    def f_dataConvert_Import(self, acFileName: str) -> list:            # dataObjectConvert() + importData()
        fpFilePath = self.f_rawDataPath(acFileName)
        if not fpFilePath.exists():   # not in Raw_Data, so check the "output files" folder (e.g. text created via f_createFile)
            fpFilePath = self.f_outputFilePath(acFileName)
        data = self.f_dataObjectConvert(fpFilePath)
        if data is None:
            raise ValueError("Data conversion failed")

        return self.f_importData(data)

    # NO DIRECT ACCESS FOR THE USER (PRIVATE)
    def f_dataObjectConvert(self, fpFilePath: Path) -> c_Data:              # returns a Data object based on the file type
        if fpFilePath.suffix.lower() in (".png", ".jpg", ".jpeg"):
            return c_ImageData(str(fpFilePath))
        elif fpFilePath.suffix.lower() == ".txt":
            return c_TextData(str(fpFilePath))
        elif fpFilePath.suffix.lower() in (".mp4", ".avi", ".mov"):
            return c_VideoData(str(fpFilePath))
        else:
            raise ValueError("Unsupported file type")

    # NO DIRECT ACCESS FOR THE USER (PRIVATE)
    def f_importData(self, data: c_Data) -> list:                       # returns the imported Data object 
        if self.dbManager is None:
            raise ValueError("A DB manager is required for database operations")
        self.dbManager.data = data
        self.dbManager.result = []
        pImporter = self.dbManager
        pImporter.f_parse()
        pImporter.f_import_toMongo()

        if self.test:
            pImporter.f_show()

        return pImporter.f_get_data()   # Not really needed right now - but maybe for future.

    # PUBLIC INTERFACE FOR THE USER
    def f_retrieveDataDB(self, acFileName: str) -> list:                 # retrieves data from the database based on the file type
        fpFilePath = self.f_rawDataPath(acFileName)
        data = self.f_dataObjectConvert(fpFilePath)
        if self.dbManager is None:
            raise ValueError("A DB manager is required for database operations")
        self.dbManager.data = data
        self.dbManager.result = []
        pImporter = self.dbManager
        pImporter.f_retrieveFromMongo()
        pImporter.f_show()
        return pImporter.f_get_data()   # Not really needed right now - but maybe for future.

    # PUBLIC INTERFACE FOR THE USER
    def f_deleteDataDB(self, acFileName: str) -> None:                 # deletes data from the database based on the file type
        fpFilePath = self.f_rawDataPath(acFileName)
        data = self.f_dataObjectConvert(fpFilePath)
        if self.dbManager is None:
            raise ValueError("A DB manager is required for database operations")
        self.dbManager.data = data
        self.dbManager.result = []
        pImporter = self.dbManager
        pImporter.f_parse()
        pImporter.f_deleteData()

    def f_createFile(self, acFileName: str, acContent: str) -> None:   # creates a text file with the given content inside the "output files" folder
        fpFilePath = self.f_outputFilePath(acFileName)

        if not fpFilePath.parent.exists():
            fpFilePath.parent.mkdir(parents=True, exist_ok=True)
        with open(fpFilePath, "w", encoding="utf-8") as f:
            f.write(acContent)
        