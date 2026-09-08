
'''
mainHelper.py

Author: Trinh Pham

This file contains helper functions for the main executable script.

'''

from pathlib import Path

try:
    from .DBManager import c_DBManager
    from .Data import c_Data, c_ImageData, c_TextData, c_VideoData
except ImportError:
    from DBManager import c_DBManager
    from Data import c_Data, c_ImageData, c_TextData, c_VideoData


# A support facade pattern for the main executable script
class c_MainHelper:
    def __init__(self, dbManager: c_DBManager | None = None, test: bool = False, deleteAll: bool = False) -> None:
        self.dbManager = dbManager          # uses the provided DB manager for this class's database operations
        self.test = test
        self.deleteAll = deleteAll

        if deleteAll:
            if self.dbManager is None:
                raise ValueError("A DB manager is required when deleteAll is True")
            self.dbManager.f_deleteDataAll()

    # PUBLIC INTERFACE FOR THE USER
    def f_dataConvert_Import(self, acFileName: str) -> list:            # dataObjectConvert() + importData()
        fpFilePath = Path(__file__).with_name(acFileName)
        data = self.f_dataObjectConvert(fpFilePath)
        

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
        fpFilePath = Path(__file__).with_name(acFileName)
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
        fpFilePath = Path(__file__).with_name(acFileName)
        data = self.f_dataObjectConvert(fpFilePath)
        if self.dbManager is None:
            raise ValueError("A DB manager is required for database operations")
        self.dbManager.data = data
        self.dbManager.result = []
        pImporter = self.dbManager
        pImporter.f_parse()
        pImporter.f_deleteData()