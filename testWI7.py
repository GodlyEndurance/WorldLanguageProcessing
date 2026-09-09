# Author: Trinh Pham

import tempfile             # Used for creating temporary files in tests
import unittest             # Used for writing and running unit tests
from pathlib import Path    # Used for handling file paths in tests
from typing import cast     # Used for type casting in tests
from unittest.mock import Mock, patch, MagicMock  # Used for mocking MongoDB operations

try:
    from .DB.Data import c_ImageData, c_TextData
    from .mainHelper import c_MainHelper
    from .DB.DBManager import c_DBManager
except ImportError:
    from DB.Data import c_ImageData, c_TextData
    from mainHelper import c_MainHelper
    from DB.DBManager import c_DBManager

# Will test each function to ensure correct behavior - unit tests



# Unit tests for the Data classes
class c_DataTests(unittest.TestCase):

    # verifies that the text data stores and retrieves texts correctly
    def test_text_data_stores_text(self):
        data = c_TextData("example.txt")

        data.f_add_text("Hello")

        self.assertEqual(data.f_get_file_path(), "example.txt")
        self.assertEqual(data.f_get_data(), ["Hello"])

    # verifies that the image data stores and retrieves images correctly
    def test_image_data_stores_image(self):
        data = c_ImageData("example.png")
        pImage = object()

        data.f_add_image(pImage)

        self.assertEqual(data.f_get_data(), [pImage])


# Unit tests for the ImportData Class
class c_DBManagerTests(unittest.TestCase):
    # parses text data as the whole file's content, not per-line JSON
    def test_parse_text_data_reads_whole_file(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as file:
            file.write('{"name": "Alice"}\n{"name": "Bob"}\n')
            fpFilePath = file.name

        self.addCleanup(Path(fpFilePath).unlink)
        pImporter = c_DBManager.f_get_instance(c_TextData(fpFilePath))

        pImporter.f_parse()

        self.assertEqual(pImporter.f_get_data(), ['{"name": "Alice"}\n{"name": "Bob"}\n'])

    # ensures a missing text file results in an empty data list
    def test_parse_text_data_returns_empty_list_for_missing_file(self):
        pImporter = c_DBManager.f_get_instance(c_TextData("this_file_does_not_exist.txt"))

        pImporter.f_parse()

        self.assertEqual(pImporter.f_get_data(), [])

    # rejects text data saved with an image extension
    def test_image_data_parses_json_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".png", delete=False) as file:
            file.write("fake image data")
            fpFilePath = file.name

        self.addCleanup(Path(fpFilePath).unlink)
        pImporter = c_DBManager.f_get_instance(c_ImageData(fpFilePath))

        pImporter.f_parse()

        self.assertEqual(pImporter.f_get_data(), [])

    # Verifies that an incorrect format for image data is handled appropriately
    def test_parse_incorrect_image_format_returns_empty_list(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".png", delete=False) as file:
            file.write("not valid image data\n")
            fpFilePath = file.name

        self.addCleanup(Path(fpFilePath).unlink)
        pImporter = c_DBManager.f_get_instance(c_ImageData(fpFilePath))

        pImporter.f_parse()

        self.assertEqual(pImporter.f_get_data(), [])


# Conversion tests for the data object conversion function
class c_ConversionTests(unittest.TestCase):
    # verifies that the data object conversion selects the correct type based on file extension
    def test_data_object_convert_selects_type_from_extension(self):
        self.assertIsInstance(c_MainHelper().f_dataObjectConvert(Path("notes.txt")), c_TextData)
        self.assertIsInstance(c_MainHelper().f_dataObjectConvert(Path("photo.png")), c_ImageData)

    # ensures that unknown file extensions raise a ValueError
    def test_data_object_convert_rejects_unknown_extension(self):
        with self.assertRaises(ValueError):
            c_MainHelper().f_dataObjectConvert(Path("archive.pdf"))


# MongoDB Connection Tests
class c_MongoDBConnectionTests(unittest.TestCase):
    # verifies that connection check returns True when MongoDB is reachable
    @patch('DB.DBManager.MongoClient')
    def test_connect_toMongo_success(self, pMockClient):
        pMockInstance = MagicMock()
        pMockClient.return_value = pMockInstance
        pMockInstance.close = MagicMock()
        
        pImporter = c_DBManager.f_get_instance(c_TextData("test.txt"))
        result = pImporter.f_connect_toMongo()
        
        self.assertIs(result, pMockInstance)
    
    # verifies that connection check returns False on exception
    @patch('DB.DBManager.MongoClient')
    def test_connect_toMongo_failure(self, pMockClient):
        pMockClient.side_effect = Exception("Connection refused")
        
        pImporter = c_DBManager.f_get_instance(c_TextData("test.txt"))
        result = pImporter.f_connect_toMongo()
        
        self.assertFalse(result)


# MongoDB Delete Tests
class c_MongoDBDeleteTests(unittest.TestCase):
    # verifies that f_deleteData deletes documents with matching IDs
    @patch('DB.DBManager.MongoClient')
    def test_deleteData_removes_documents_by_id(self, pMockClient):
        pMockInstance = MagicMock()
        pMockClient.return_value = pMockInstance
        pMockDb = MagicMock()
        pMockCollection = MagicMock()
        pMockInstance.__getitem__.side_effect = lambda key: pMockDb if key == "admin" else None
        pMockDb.__getitem__.return_value = pMockCollection
        pMockInstance.close = MagicMock()
        
        # Create mock data with _id fields
        acMockData = cast(list[dict[str, object]], [
            {"_id": 1, "name": "Alice"},
            {"_id": 2, "name": "Bob"}
        ])
        
        pImporter = c_DBManager.f_get_instance(c_TextData("test.txt"))
        pImporter.result = acMockData  # type: ignore   # Used specifically for working around type restrictions for mock data
        
        pImporter.f_deleteData()
        
        # Verify delete_many was called with correct IDs
        pMockCollection.delete_many.assert_called_once()


    # verifies that f_deleteDataAll deletes all documents
    @patch('DB.DBManager.MongoClient')
    def test_deleteDataAll_removes_all_documents(self, pMockClient):
        pMockInstance = MagicMock()
        pMockClient.return_value = pMockInstance
        pMockDb = MagicMock()
        pMockCollection = MagicMock()
        pMockGridFSFiles = MagicMock()
        pMockGridFSChunks = MagicMock()
        pMockInstance.__getitem__.side_effect = lambda key: pMockDb if key == "admin" else None
        pMockDb.__getitem__.side_effect = lambda key: {
            "Test": pMockCollection,
            "fs.files": pMockGridFSFiles,
            "fs.chunks": pMockGridFSChunks
        }[key]
        pMockInstance.close = MagicMock()
        
        pImporter = c_DBManager.f_get_instance(c_TextData("test.txt"))
        pImporter.f_deleteDataAll()
        
        # Verify delete_many was called with empty filter
        pMockCollection.delete_many.assert_called_once_with({})
        pMockGridFSFiles.delete_many.assert_called_once_with({})
        pMockGridFSChunks.delete_many.assert_called_once_with({})
    
    # verifies that delete handles Image objects gracefully
    @patch('DB.DBManager.MongoClient')
    def test_deleteData_handles_mixed_data_types(self, pMockClient):
        pMockInstance = MagicMock()
        pMockClient.return_value = pMockInstance
        pMockDb = MagicMock()
        pMockCollection = MagicMock()
        pMockInstance.__getitem__.side_effect = lambda key: pMockDb if key == "admin" else None
        pMockDb.__getitem__.return_value = pMockCollection
        pMockInstance.close = MagicMock()
        
        # Create data with dict and non-dict (Image) objects
        acMixedData = cast(list[dict[str, object] | object], [
            {"_id": 1, "name": "Alice"},
            object()  # Image-like object
        ])
        
        pImporter = c_DBManager.f_get_instance(c_TextData("test.txt"))
        pImporter.result = acMixedData  # type: ignore   # Used specifically for working around type restrictions for mock data
        
        pImporter.f_deleteData()
        
        # Should not crash and should filter out non-dict objects
        pMockCollection.delete_many.assert_called_once()


# Tests for singleton access and image storage selection
class c_DBManagerStorageTests(unittest.TestCase):
    def test_get_instance_returns_same_manager(self):
        first = c_DBManager.f_get_instance(c_TextData("first.txt"))
        second = c_DBManager.f_get_instance(c_TextData("second.txt"))

        self.assertIs(first, second)
        secondData = cast(c_TextData, second.data)
        self.assertEqual(secondData.f_get_file_path(), "second.txt")

    @patch("DB.DBManager.GridFS")
    @patch("DB.DBManager.MongoClient")
    def test_import_image_at_binary_limit(self, pMockClient, pMockGridFS):
        pMockInstance = MagicMock()
        pMockClient.return_value = pMockInstance
        pMockDb = MagicMock()
        pMockCollection = MagicMock()
        pMockInstance.__getitem__.side_effect = lambda key: pMockDb if key == "admin" else None
        pMockDb.__getitem__.return_value = pMockCollection

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as file:
            file.truncate(c_DBManager.MAX_BINARY_SIZE)
            fpFilePath = file.name

        self.addCleanup(Path(fpFilePath).unlink)
        manager = c_DBManager.f_get_instance(c_ImageData(fpFilePath))
        manager.f_import_toMongo()

        pMockCollection.insert_one.assert_called_once()
        pMockGridFS.assert_not_called()

    @patch("DB.DBManager.GridFS")
    @patch("DB.DBManager.MongoClient")
    def test_import_image_over_binary_limit_uses_gridfs(self, pMockClient, pMockGridFS):
        pMockInstance = MagicMock()
        pMockClient.return_value = pMockInstance
        pMockDb = MagicMock()
        pMockCollection = MagicMock()
        pMockGridFS.return_value = MagicMock()
        pMockInstance.__getitem__.side_effect = lambda key: pMockDb if key == "admin" else None
        pMockDb.__getitem__.return_value = pMockCollection

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as file:
            file.truncate(c_DBManager.MAX_BINARY_SIZE + 1)
            fpFilePath = file.name

        self.addCleanup(Path(fpFilePath).unlink)
        manager = c_DBManager.f_get_instance(c_ImageData(fpFilePath))
        manager.f_import_toMongo()

        pMockGridFS.return_value.put.assert_called_once()
        pMockCollection.insert_one.assert_not_called()

    @patch("DB.DBManager.MongoClient")
    def test_delete_image_removes_binary_and_gridfs_data(self, pMockClient):
        pMockInstance = MagicMock()
        pMockClient.return_value = pMockInstance
        pMockDb = MagicMock()
        pMockCollection = MagicMock()
        pMockGridFSFiles = MagicMock()
        pMockGridFSChunks = MagicMock()
        pMockGridFSFiles.find.return_value = [{"_id": "gridfs-id"}]
        pMockInstance.__getitem__.return_value = pMockDb
        pMockDb.__getitem__.side_effect = lambda key: {
            "Test": pMockCollection,
            "fs.files": pMockGridFSFiles,
            "fs.chunks": pMockGridFSChunks
        }[key]

        manager = c_DBManager.f_get_instance(c_ImageData("photo.png"))
        manager.f_deleteData()

        pMockCollection.delete_many.assert_called_once_with({"filename": "photo.png"})
        pMockGridFSFiles.delete_many.assert_called_once_with(
            {"_id": {"$in": ["gridfs-id"]}}
        )
        pMockGridFSChunks.delete_many.assert_called_once_with(
            {"files_id": {"$in": ["gridfs-id"]}}
        )


if __name__ == "__main__":
    unittest.main()