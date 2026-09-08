
'''
import.py

Author: Trinh Pham

This script is a class for importing data into a MongoDB database. 

Inputs: Data.txt
'''

'''
Class for importing data into MongoDB.
Uses dependency injection for data.txt input. 
'''

import logging                  # for logging errors and information
import mimetypes                # for image file (binary form, ≤16 MB). Tells MongoDB what kind of file the binary data represents.
import os                       # for os.startfile (launching the default video player on Windows)
import subprocess               # for launching the default video player on macOS/Linux
import sys                      # for detecting the current OS platform
import tempfile                 # for writing retrieved video bytes to a playable file on disk
import traceback                # To detail what line an error occurred on
from io import BytesIO          # for decoding retrieved image bytes in-memory
from pathlib import Path        # for handling file paths
from PIL import Image           # If not installed in the mongoenv, run: python -m pip install Pillow pymongo

try:
    from . import Data
except ImportError:
    import Data

try:
    from . import TemporaryCache
except ImportError:
    import TemporaryCache


from pymongo import MongoClient
from bson.binary import Binary
from gridfs import GridFS


logger = logging.getLogger(__name__)
_CONSTRUCTOR_TOKEN = object()


# This class is a singleton, such that there is only one instance of it throughout the application.
# It will manage the interaction between the data and the database
class c_DBManager:
    # Data
    MONGODB_URI = "mongodb://localhost:27017/"
    DB_NAME = "admin"
    COLLECTION_NAME = "Test"
    MAX_BINARY_SIZE = 16 * 1024 * 1024                  # Maximum size for binary data (16 MB)
    _instance = None                                    # Singleton instance of the class
    
    data: Data.c_Data | None                            # for using Data object to access its methods (getFilePath and getData)
    result: list[dict[str, object] | Image.Image | str] # Image.Image for parsed images; str for parsed videos (file path) or text (full content)
                                                        # A list of all Data objects that have been parsed and are ready for database operations

    temp_cache: TemporaryCache.c_TemporaryCache          # Encapsulates the filename dedup cache used by import/delete

    # Methods

    # None data type is for when no Data object is provided during initialization (for deleteDataAll operation (see mainHelper constructor))
    def __new__(cls, data: Data.c_Data | None = None, _token: object = None): # The cls parameter represents the class itself, used for creating a singleton instance
        if _token is not _CONSTRUCTOR_TOKEN:                    # Ensures that the constructor is only called through the f_get_instance method
            raise TypeError("Use c_DBManager.f_get_instance() to access the DB manager")
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, data: Data.c_Data | None = None, _token: object = None) -> None:
        if _token is not _CONSTRUCTOR_TOKEN:
            raise TypeError("Use c_DBManager.f_get_instance() to access the DB manager")
        self.data = data
        self.result = []
        self.temp_cache = TemporaryCache.c_TemporaryCache()

    @classmethod
    def f_get_instance(cls, data: Data.c_Data | None = None):
        return cls(data, _CONSTRUCTOR_TOKEN)            # Returns the singleton instance of the class

    def f_connect_toMongo(self) -> MongoClient | None:
        try:
            pClient = MongoClient(self.MONGODB_URI)
            pDb = pClient[self.DB_NAME]
            pCollection = pDb[self.COLLECTION_NAME]
            return pClient
        except Exception as e:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to connect to MongoDB at line {iLineNumber}: {e}")
            return None

    def f_deleteData(self) -> None:    # Deletes the specific data object from MongoDB
        try:
            pClient = MongoClient(self.MONGODB_URI)
            pDb = pClient[self.DB_NAME]
            pCollection = pDb[self.COLLECTION_NAME]
            pClient.close()
        except Exception as e:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to connect to MongoDB at line {iLineNumber}: {e}")
            return

        try:
            if isinstance(self.data, (Data.c_TextData, Data.c_ImageData, Data.c_VideoData)):    # all three are now stored the same way: one document per filename
                acFileName = Path(self.data.f_get_file_path()).name
                pCollection.delete_many({"filename": acFileName})

                pGridFSFiles = pDb["fs.files"]                  # fs is MongoDB's GridFS collection for file metadata
                pGridFSChunks = pDb["fs.chunks"]                # fs.chunks stores the actual file data in chunks
                aFileIds = [
                    document["_id"]
                    for document in pGridFSFiles.find({"filename": acFileName})
                ]
                if aFileIds:
                    pGridFSFiles.delete_many({"_id": {"$in": aFileIds}})
                    pGridFSChunks.delete_many({"files_id": {"$in": aFileIds}})
                else:
                    print(f"No GridFS files found for filename: {acFileName}")

                if self.temp_cache.temp_storage_during_execution is not None:      # keep the duplicate-name cache in sync with the deletion
                    self.temp_cache.f_remove_from_temp_storage(acFileName)

            pClient.close()
        except Exception as e:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to delete from MongoDB at line {iLineNumber}: {e}")

    def f_deleteDataAll(self) -> None:              # Deletes all text and image files from MongoDB
        try:
            pClient = MongoClient(self.MONGODB_URI)
            pDb = pClient[self.DB_NAME]
            pCollection = pDb[self.COLLECTION_NAME]
        except Exception as e:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to connect to MongoDB at line {iLineNumber}: {e}")
            return

        try:
            pCollection.delete_many({})
            pDb["fs.files"].delete_many({})
            pDb["fs.chunks"].delete_many({})
            pClient.close()
        except Exception as e:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to delete from MongoDB at line {iLineNumber}: {e}")

    def f_get_data(self) -> list[dict[str, object] | Image.Image | str]:          # Not really used right now - just used as a getter for the future
        # Simply returns the result list, which contains the data retrieved from the Data object
        return self.result

    def f_retrieveFromMongo(self) -> None:      # Retrieves data straight from MongoDB (not the local file) and populates the result list
        if not isinstance(self.data, Data.c_Data):            # inverse guard clause
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.error(f"retrieveFromMongo() requires a Data object at line {iLineNumber}")
            return

        try:
            pClient = MongoClient(self.MONGODB_URI)
            pDb = pClient[self.DB_NAME]
            pCollection = pDb[self.COLLECTION_NAME]
        except Exception as e:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to connect to MongoDB at line {iLineNumber}: {e}")
            return

        try:
            if isinstance(self.data, (Data.c_TextData, Data.c_ImageData, Data.c_VideoData)):    # all three are looked up the same way, by filename
                acFileName = Path(self.data.f_get_file_path()).name
                aiFileBytes = None    # holds the raw data fetched from MongoDB/GridFS (str for text, bytes for image/video)

                pDocument = pCollection.find_one({"filename": acFileName})
                if pDocument is not None:   # if pDocument is found
                    aiFileBytes = pDocument["data"]
                else:   #look with GridFS
                    pGridFS = GridFS(pDb)
                    if pGridFS.exists({"filename": acFileName}):
                        aiFileBytes = pGridFS.get_last_version(acFileName).read()

                if aiFileBytes is None:   # if no data was found in MongoDB/GridFS
                    self.result = []
                    iLineNumber = traceback.extract_stack()[-1].lineno
                    logger.error(f"No data found in MongoDB for {acFileName} at line {iLineNumber}")

                elif isinstance(self.data, Data.c_TextData):
                    acText = aiFileBytes.decode("utf-8", errors="replace") if isinstance(aiFileBytes, (bytes, bytearray)) else str(aiFileBytes)
                    self.data.f_add_text(acText)
                    self.result = self.data.f_get_data()
                elif isinstance(self.data, Data.c_ImageData):
                    pImage = Image.open(BytesIO(aiFileBytes))
                    self.data.f_add_image(pImage)
                    self.result = self.data.f_get_data()
                else:   # c_VideoData - write to a temp file since videos are played by an external OS player, rather than decoded in-memory
                    acSuffix = Path(acFileName).suffix
                    with tempfile.NamedTemporaryFile(suffix=acSuffix, delete=False) as pTempFile:
                        pTempFile.write(aiFileBytes)
                        fpTempPath = pTempFile.name
                    self.data.f_add_video(fpTempPath)
                    self.result = self.data.f_get_data()
            else:
                iLineNumber = traceback.extract_stack()[-1].lineno
                logger.error(f"Unsupported data type for retrieval at line {iLineNumber}")
        except Exception as e:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to retrieve from MongoDB at line {iLineNumber}: {e}")
        finally:
            pClient.close()

    def f_import_toMongo(self) -> None:         # imports some data (text, image) into MongoDB
        try:
            pClient = MongoClient(self.MONGODB_URI)
            pDb = pClient[self.DB_NAME]
            pCollection = pDb[self.COLLECTION_NAME]
            pClient.close()
        except Exception as e:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to connect to MongoDB at line {iLineNumber}: {e}")
            return

        try:
            if isinstance(self.data, (Data.c_TextData, Data.c_ImageData, Data.c_VideoData)):
                fpFilePath = self.data.f_get_file_path()
                if self.temp_cache.temp_storage_during_execution is None:      # populate the filename cache once per execution
                    self.temp_cache.f_add_temp_storage(pCollection)
                acFileName = self.temp_cache.f_get_unique_filename(Path(fpFilePath).name)
                acContentType = mimetypes.guess_type(fpFilePath)[0]
                acContentType = acContentType or "application/octet-stream"
                bWithinBinaryLimit = Path(fpFilePath).stat().st_size <= self.MAX_BINARY_SIZE

                if isinstance(self.data, Data.c_TextData) and bWithinBinaryLimit:
                    # Store the whole processed output (e.g. a future OCR result) under its filename, not one document per JSON line
                    acTextContent = self.result[0] if self.result else ""
                    pCollection.insert_one({
                        "filename": acFileName,
                        "content_type": acContentType,
                        "data": acTextContent
                    })
                elif bWithinBinaryLimit:     # If ≤16MB
                    with open(fpFilePath, "rb") as file:
                        abImageData = Binary(file.read())

                    pCollection.insert_one({
                        "filename": acFileName,
                        "content_type": acContentType,
                        "data": abImageData
                    })
                else:
                    with open(fpFilePath, "rb") as file:                        # If >16 MB
                        GridFS(pDb).put(
                            file,
                            filename=acFileName,
                            content_type=acContentType
                        )
            pClient.close()
        except Exception as e:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to import to MongoDB at line {iLineNumber}: {e}")

    def f_parse(self) -> None:                                      # Parse the data file and populate the result list accordingly
        # Minimum guarantee: self.data must be a Data object before parsing
        if not isinstance(self.data, Data.c_Data):            # inverse guard clause
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.error(f"parse() requires a Data object at line {iLineNumber}")
            return

        fpFilePath = self.data.f_get_file_path()    # More writability for subsequent file operations

        if isinstance(self.data, Data.c_TextData):
            try:
                with open(fpFilePath, 'r') as file:
                    acFullText = file.read()      # store the whole processed output (e.g. a future OCR result), not one doc per JSON line
                self.data.f_add_text(acFullText)
                self.result = self.data.f_get_data()
            except OSError:
                self.result = []
                iLineNumber = traceback.extract_stack()[-1].lineno
                logger.error(f"Invalid text file at line {iLineNumber}: {fpFilePath}")
        elif isinstance(self.data, Data.c_ImageData):   # PIL decodes the images
            try:
                pImage = Image.open(fpFilePath)
                self.data.f_add_image(pImage)
                self.result = self.data.f_get_data()
            except (Image.UnidentifiedImageError, OSError):
                self.result = []
                iLineNumber = traceback.extract_stack()[-1].lineno
                logger.error(f"Invalid image file at line {iLineNumber}: {fpFilePath}")
        elif isinstance(self.data, Data.c_VideoData):
            try:
                if not Path(fpFilePath).is_file():          # PIL cannot decode video, so just verify the file exists
                    raise OSError(f"Video file not found: {fpFilePath}")
                self.data.f_add_video(fpFilePath)
                self.result = self.data.f_get_data()
            except OSError:
                self.result = []
                iLineNumber = traceback.extract_stack()[-1].lineno
                logger.error(f"Invalid video file at line {iLineNumber}: {fpFilePath}")
        else:
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.error(f"Unsupported data type for parsing at line {iLineNumber}")

    def f_show(self) -> None:                                         # Show a preview of the data (first and last items if more than 2)    
        # Size of the preview list optimization
        if len(self.result) <= 2:
            aPreview = self.result
        else:
            aPreview = [self.result[0], self.result[-1]]

        # showing the preview of the data
        if isinstance(self.data, Data.c_TextData):
            for doc in aPreview:
                print(doc)
        elif isinstance(self.data, Data.c_ImageData):
            for img in aPreview:
                if isinstance(img, Image.Image):
                    img.show()
        elif isinstance(self.data, Data.c_VideoData):
            for video_path in aPreview:
                if isinstance(video_path, str):
                    try:
                        if sys.platform == "darwin":    #MacOS
                            subprocess.run(["open", video_path], check=True) 
                        elif sys.platform.startswith("win"):  # Windows
                            os.startfile(video_path)  # type: ignore[attr-defined]
                        else:   # Linux and other platforms
                            subprocess.run(["xdg-open", video_path], check=True)
                    except (OSError, subprocess.SubprocessError) as e:
                        print(f"OS platform not support: {sys.platform}")
                        iLineNumber = traceback.extract_stack()[-1].lineno
                        logger.error(f"Failed to open video at line {iLineNumber}: {e}")