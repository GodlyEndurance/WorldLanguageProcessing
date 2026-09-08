

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
    from .DBManager import c_DBManager
    from .mainHelper import c_MainHelper
except ImportError:
    from DBManager import c_DBManager
    from mainHelper import c_MainHelper


# Note: Testing mode (True) is for testing the import function works correctly by showing the imported data

# ------------------------------------------------------------------------------------------------------------
    
def main():
    dBM = c_DBManager.f_get_instance()

    helper = c_MainHelper(dBM, test=False, deleteAll=False)
    # TEXT
    # helper.f_dataConvert_Import("Data.txt")
    # helper.f_dataConvert_Import("Data.txt")
    # helper.f_retrieveDataDB("Data.txt")
    # helper.f_deleteDataDB("Data.txt")

    # IMAGE
    # helper.f_dataConvert_Import("MockPicture.png")
    # helper.f_retrieveDataDB("MockPicture.png")
    # helper.f_deleteDataDB("MockPicture.png")

    # VIDEO
    # helper.f_dataConvert_Import("MockVideo.mov")
    # helper.f_retrieveDataDB("MockVideo.mov")
    # helper.f_deleteDataDB("MockVideo.mov")

# ------------------------------------------------------------------------------------------------------------



# ------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    main()