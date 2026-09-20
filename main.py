

'''
main.py

Author: Trinh Pham

This is the executable script for the project.
This will instantiate the main classes of the project and inject the necessary dependencies.


'''

'''
Context: 
1. MongoDB is a NoSQL database that stores data in JSON, BSON, and XML documents.
2. NoSQL databases allow for horizontal scaling, such that there can be many servers instead of just one for storing data.
'''

'''
Objectives:
1. To import data into a MongoDB
    -> Requires a running MongoDB instance and code to connect to it.
2. Have mock data to import into the MongoDB database.

Operations:
1. Convert a file into a Data object based on its type.
2. Import the Data object into MongoDB.
3. Delete data from MongoDB.
4. Retrieve data from MongoDB.
5. Optionally delete all data from MongoDB (for testing purposes).

NOTE: FOR THE UI INTEGRATION, THE DATABASE SHOULD BE DISPLAYED. 
- This means that files that are duplicates and are appended with (1), (2), etc. to preserve canonical form will have to have a 
delete button to delete said file. Additionally, there can be some textbox that allows the user to delete said file by copying 
and pasting the exact file name, including any (1), (2), etc.

'''



try:
    from .DB.DBManager import c_DBManager
    from .mainHelper import c_MainHelper
    from .OCR.OCR import c_OCR, c_GoogleCloudOCR, c_TesseractOCR
    from .OCR.OCR_manager import c_OCRManager
except ImportError:
    from DB.DBManager import c_DBManager
    from mainHelper import c_MainHelper
    from OCR.OCR import c_OCR, c_GoogleCloudOCR, c_TesseractOCR
    from OCR.OCR_manager import c_OCRManager


# Note: Testing mode (True) is for testing the import function works correctly by showing the imported data

# ------------------------------------------------------------------------------------------------------------
    
def main():

    oCRM = c_OCRManager.f_get_instance()
    dBM = c_DBManager.f_get_instance()

    # Facade pattern
    helper = c_MainHelper(dBM, oCRM, test=False, deleteAll=False)

    # Operations of Facade pattern:
    '''
        OCR
        1. f_assignOCR            Assign the OCR engine to use
        2. f_processFileOCR       Process the source file using the assigned OCR engine
        3. f_createFile           Create a text file with the organized text
        4. f_uploadFileOCR        Upload the file to the OCR engine's storage (if applicable) and return the remote path or URL
        5. f_organizeTextOCR      Organize the already-detected text
        6. f_uploadFileOCR        Upload the file to the OCR engine's storage (if applicable) and return the remote path or URL
        7. f_organizeTextOCR      Organize the already-detected text

        Database
        1. f_dataConvert_Import   Convert the text file into a Data object and import it into MongoDB
        2. f_retrieveDataDB       Retrieve data from MongoDB based on the file type
        3. f_deleteDataDB         Delete data from MongoDB based on the file type
        4. f_adjustName           Rename the local output file and its stored DB filename if already imported
        5. f_deleteAllDataDB     Delete all data from MongoDB (for testing purposes)
    '''

    # Assign the OCR engine to use before processing any files
    helper.f_assignOCR("GoogleCloud")  # Assign the OCR engine to Google Cloud

    # Prepare the list of source files and their corresponding output files
    # ==========================================================================================================
    sourceName = []
    fileName = []
    
    """ sourceName.append("魔王様は回復魔術を極めたいC3.MP4")
    fileName.append("魔王様は回復魔術を極めたいC3.txt") """

    # Match each source file to its corresponding output file by the same index.
    # Example: sourceName[0] -> fileName[0], sourceName[1] -> fileName[1]
    pairedFiles = {}
    for i in range(len(sourceName)):
        pairedFiles[sourceName[i]] = fileName[i]

    # helper.f_uploadFileOCR("E7C3E4.MP4")  # Process the file using the assigned OCR engine

    for source_file, output_file in pairedFiles.items():
        if not source_file:
            return
        
        print(f"Processing source file: {source_file} with output file: {output_file}")
        rawText = helper.f_processFileOCR(source_file)  # Detect on-screen text in the video and print it
        rawText = helper.f_organizeTextOCR(rawText)
        # NOTE: dialogue word-splitting is intentionally not done here; main2.py's vocab pipeline
        # re-splits this output file itself and expects it to still have intact DIALOGUE sentences.

        helper.f_createFile(output_file, rawText)  # Create a text file with the organized text
        helper.f_dataConvert_Import(output_file)
    # ==========================================================================================================


    # TEXT ========================

    # CREATE
    # helper.f_createFile(output_file, rawText)  # Create a text file with the organized text
    # helper.f_dataConvert_Import(output_file)


    # RETRIEVE
    # helper.f_retrieveDataDB(fileName)

    # DELETE
    # helper.f_deleteDataDB("Data.txt")

    """  helper.f_adjustName("Game1.txt", "E7C3E1.txt")
    helper.f_adjustName("Game2.txt", "E7C3E2.txt")
    helper.f_adjustName("Game3.txt", "E7C3E3.txt") """

    # IMAGE ========================
    # helper.f_dataConvert_Import("MockPicture.png")
    # helper.f_retrieveDataDB("MockPicture.png")
    # helper.f_deleteDataDB("MockPicture.png")

    # VIDEO ========================
    # helper.f_dataConvert_Import("MockVideo.mov")
    # helper.f_retrieveDataDB("MockVideo.mov")
    # helper.f_deleteDataDB("MockVideo.mov")

# ------------------------------------------------------------------------------------------------------------



# ------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    main()