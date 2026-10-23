
'''
DBManager1.py

Author: Trinh Pham

Singleton class for importing, retrieving, renaming and deleting data (text, image, video) in MongoDB.
Uses dependency injection for the Data object.
'''

import logging                  # for logging errors and information
import mimetypes                # tells MongoDB what kind of file the binary data represents
import os                       # for os.startfile (launching the default video player on Windows)
import subprocess               # for launching the default video player on macOS/Linux
import sys                      # for detecting the current OS platform
import tempfile                 # for writing retrieved video bytes to a playable file on disk
from contextlib import contextmanager
from io import BytesIO          # for decoding retrieved image bytes in-memory
from pathlib import Path        # for handling file paths
from PIL import Image           # If not installed in the mongoenv, run: python -m pip install Pillow pymongo

try:
    from . import Data
except ImportError:
    import DB.Data as Data

try:
    from . import TemporaryCache
except ImportError:
    import DB.TemporaryCache as TemporaryCache

from pymongo import MongoClient
from bson.binary import Binary
from gridfs import GridFS


logger = logging.getLogger(__name__)
_CONSTRUCTOR_TOKEN = object()
_STORABLE = (Data.c_TextData, Data.c_ImageData, Data.c_VideoData)    # data types that are stored one document per filename


# This class is a singleton, such that there is only one instance of it throughout the application.
# It will manage the interaction between the data and the database
class c_DBManager:
    MONGODB_URI = "mongodb://localhost:27017/"
    DB_NAME = "admin"
    COLLECTION_NAME = "Test"
    MAX_BINARY_SIZE = 16 * 1024 * 1024                  # Maximum size for binary data (16 MB); larger files go to GridFS
    _instance = None                                    # Singleton instance of the class

    data: Data.c_Data | None                            # None when no Data object is provided (e.g. deleteDataAll; see mainHelper constructor)
    result: list[dict[str, object] | Image.Image | str] # Image.Image for images; str for video (file path) or text (full content)
    temp_cache: TemporaryCache.c_TemporaryCache         # Filename dedup cache used by import/delete/rename

    def __new__(cls, data: Data.c_Data | None = None, _token: object = None):
        if _token is not _CONSTRUCTOR_TOKEN:            # Ensures that the constructor is only called through f_get_instance
            raise TypeError("Use c_DBManager.f_get_instance() to access the DB manager")
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, data: Data.c_Data | None = None, _token: object = None) -> None:
        self.data = data
        self.result = []
        self.temp_cache = TemporaryCache.c_TemporaryCache()

    @classmethod    # for the singleton pattern
    def f_get_instance(cls, data: Data.c_Data | None = None):
        return cls(data, _CONSTRUCTOR_TOKEN)

    @contextmanager    # from contextlib and turns a generator function (one with a yield) into a context manager
                        # "Yields" pauses the function it is in, and hands out the value binded to the Yields
                        # So, if main called the generator function f() (with the Yields), then
                            # the other functions after f() (inside main()) will execute and return its output
                            # Afterwards, the generator function resumes from the yield statement with all its local variables intact.
                            # Then, if there is a finally within f(), it will execute immediately after.
                        # The next request resumes it from that same line, with all its local variables intact.
    def _database(self):                      # opens a MongoDB connection and always closes it afterwards
        pClient = MongoClient(self.MONGODB_URI)
        try:
            yield pClient[self.DB_NAME]
        finally:
            pClient.close()
    # DONE 

    def _file_name(self) -> str:
        return Path(self.data.f_get_file_path()).name

    def f_connect_toMongo(self) -> MongoClient | None:
        try:
            return MongoClient(self.MONGODB_URI)
        except Exception:
            logger.exception("Failed to connect to MongoDB")    # logs the traceback too; falls through to return None
            return None

    def f_deleteData(self) -> None:                     # Deletes the specific data object from MongoDB
        if not isinstance(self.data, _STORABLE):
            return
        try:
            with self._database() as pDb:
                acFileName = self._file_name()
                pDb[self.COLLECTION_NAME].delete_many({"filename": acFileName})

                aFileIds = [d["_id"] for d in pDb["fs.files"].find({"filename": acFileName})]   # fs.files/fs.chunks are GridFS's metadata/data collections
                if aFileIds:
                    pDb["fs.files"].delete_many({"_id": {"$in": aFileIds}})
                    pDb["fs.chunks"].delete_many({"files_id": {"$in": aFileIds}})
                else:
                    print(f"No GridFS files found for filename: {acFileName}")

                if self.temp_cache.temp_storage_during_execution is not None:   # keep the duplicate-name cache in sync
                    self.temp_cache.f_remove_from_temp_storage(acFileName)
        except Exception as e:
            logger.exception(f"Failed to delete from MongoDB: {e}")

    def f_deleteDataAll(self) -> None:                  # Deletes everything from the collection and GridFS
        try:
            with self._database() as pDb:
                for acName in (self.COLLECTION_NAME, "fs.files", "fs.chunks"):
                    pDb[acName].delete_many({})
        except Exception as e:
            logger.exception(f"Failed to delete from MongoDB: {e}")

    def f_renameData(self, acOldFileName: str, acNewFileName: str) -> bool:    # Renames a stored filename in the collection or GridFS; True if a match was renamed
        try:
            with self._database() as pDb:
                pCollection, pGridFSFiles = pDb[self.COLLECTION_NAME], pDb["fs.files"]
                if pCollection.find_one({"filename": acNewFileName}) or pGridFSFiles.find_one({"filename": acNewFileName}):
                    logger.error(f"Cannot rename: a document named {acNewFileName!r} already exists")
                    return False

                aUpdate = ({"filename": acOldFileName}, {"$set": {"filename": acNewFileName}})
                pResult = pCollection.update_one(*aUpdate)
                if pResult.matched_count == 0:          # not in the regular collection, so it must be a GridFS-stored file
                    pResult = pGridFSFiles.update_one(*aUpdate)

                if pResult.matched_count == 0:
                    logger.error(f"No document found to rename: {acOldFileName!r}")
                    return False
                self.temp_cache.f_rename_in_temp_storage(acOldFileName, acNewFileName)
                return True
        except Exception as e:
            logger.exception(f"Failed to rename in MongoDB: {e}")
            return False

    def f_get_data(self) -> list[dict[str, object] | Image.Image | str]:    # Getter for the result list
        return self.result

    def f_retrieveFromMongo(self) -> None:              # Retrieves data from MongoDB (not the local file) and populates the result list
        if not isinstance(self.data, _STORABLE):
            logger.error("retrieveFromMongo() requires a text, image or video Data object")
            return

        try:
            with self._database() as pDb:
                acFileName = self._file_name()
                pDocument = pDb[self.COLLECTION_NAME].find_one({"filename": acFileName})
                if pDocument is not None:
                    aiFileBytes = pDocument["data"]     # str for text, bytes for image/video
                else:                                   # look in GridFS
                    pGridFS = GridFS(pDb)
                    aiFileBytes = pGridFS.get_last_version(acFileName).read() if pGridFS.exists({"filename": acFileName}) else None

            if aiFileBytes is None:
                self.result = []
                logger.error(f"No data found in MongoDB for {acFileName}")
            elif isinstance(self.data, Data.c_TextData):
                self.data.f_add_text(aiFileBytes.decode("utf-8", errors="replace") if isinstance(aiFileBytes, (bytes, bytearray)) else str(aiFileBytes))
                self.result = self.data.f_get_data()
            elif isinstance(self.data, Data.c_ImageData):
                self.data.f_add_image(Image.open(BytesIO(aiFileBytes)))
                self.result = self.data.f_get_data()
            else:                                       # video: write to a temp file since it is played by an external OS player
                with tempfile.NamedTemporaryFile(suffix=Path(acFileName).suffix, delete=False) as pTempFile:
                    pTempFile.write(aiFileBytes)
                self.data.f_add_video(pTempFile.name)
                self.result = self.data.f_get_data()
        except Exception as e:
            logger.exception(f"Failed to retrieve from MongoDB: {e}")

    def f_import_toMongo(self) -> None:                 # Imports the data (text, image, video) into MongoDB
        if not isinstance(self.data, _STORABLE):
            return
        try:
            with self._database() as pDb:
                pCollection = pDb[self.COLLECTION_NAME]
                fpFilePath = self.data.f_get_file_path()
                if self.temp_cache.temp_storage_during_execution is None:      # populate the filename cache once per execution
                    self.temp_cache.f_add_temp_storage(pCollection)
                acFileName = self.temp_cache.f_get_unique_filename(Path(fpFilePath).name)
                acContentType = mimetypes.guess_type(fpFilePath)[0] or "application/octet-stream"

                if Path(fpFilePath).stat().st_size > self.MAX_BINARY_SIZE:     # >16 MB
                    with open(fpFilePath, "rb") as file:
                        GridFS(pDb).put(file, filename=acFileName, content_type=acContentType)
                    return

                if isinstance(self.data, Data.c_TextData):
                    # Store the whole processed output (e.g. a future OCR result) under its filename, not one document per line
                    pContent = self.result[0] if self.result else ""
                else:
                    pContent = Binary(Path(fpFilePath).read_bytes())
                pCollection.insert_one({"filename": acFileName, "content_type": acContentType, "data": pContent})
        except Exception as e:
            logger.exception(f"Failed to import to MongoDB: {e}")

    def f_parse(self) -> None:                          # Parses the data file and populates the result list
        if not isinstance(self.data, Data.c_Data):
            logger.error("parse() requires a Data object")
            return

        fpFilePath = self.data.f_get_file_path()
        try:
            if isinstance(self.data, Data.c_TextData):
                self.data.f_add_text(Path(fpFilePath).read_text())     # the whole processed output, not one doc per line
            elif isinstance(self.data, Data.c_ImageData):
                self.data.f_add_image(Image.open(fpFilePath))          # PIL decodes the images
            elif isinstance(self.data, Data.c_VideoData):
                if not Path(fpFilePath).is_file():                     # PIL cannot decode video, so just verify the file exists
                    raise OSError(f"Video file not found: {fpFilePath}")
                self.data.f_add_video(fpFilePath)
            else:
                logger.error("Unsupported data type for parsing")
                return
            self.result = self.data.f_get_data()
        except OSError:                                 # includes PIL's UnidentifiedImageError
            self.result = []
            logger.error(f"Invalid {type(self.data).__name__} file: {fpFilePath}")

    @staticmethod
    def _open_video(acPath: str) -> None:               # launches the default video player for the current OS
        try:
            if sys.platform.startswith("win"):
                os.startfile(acPath)  # type: ignore[attr-defined]
            else:
                subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", acPath], check=True)
        except (OSError, subprocess.SubprocessError) as e:
            print(f"OS platform not support: {sys.platform}")
            logger.error(f"Failed to open video: {e}")

    def f_show(self) -> None:                           # Shows a preview of the data (first and last items if more than 2)
        aPreview = self.result if len(self.result) <= 2 else [self.result[0], self.result[-1]]

        for pItem in aPreview:
            if isinstance(self.data, Data.c_TextData):
                print(pItem)
            elif isinstance(self.data, Data.c_ImageData) and isinstance(pItem, Image.Image):
                pItem.show()
            elif isinstance(self.data, Data.c_VideoData) and isinstance(pItem, str):
                self._open_video(pItem)
