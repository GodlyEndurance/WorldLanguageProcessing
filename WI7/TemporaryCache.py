
'''TemporaryCache.py

Author: Trinh Pham

This module provides a temporary cache for storing data during execution.
Caches known MongoDB/GridFS filenames during one execution and resolves "(1)", "(2)", etc. suffixes for duplicates.
'''

import logging
import traceback
from pathlib import Path

logger = logging.getLogger(__name__)


class c_TemporaryCache:
    temp_storage_during_execution: dict[str, object] | None   # None until populated; distinguishes "not yet loaded" from "loaded but empty"

    def __init__(self):
        self.temp_storage_during_execution = None

    def f_add_temp_storage(self, pCollection) -> None:   # Caches existing MongoDB/GridFS filenames once per execution, so duplicate checks avoid a DB query per file
        try:
            pDb = pCollection.database
            aAllFileNames = pCollection.distinct("filename") + pDb["fs.files"].distinct("filename")
            self.temp_storage_during_execution = {acFileName: None for acFileName in aAllFileNames}
        except Exception as e:
            self.temp_storage_during_execution = {}
            iLineNumber = traceback.extract_stack()[-1].lineno
            logger.exception(f"Failed to set up temp storage at line {iLineNumber}: {e}")

    # True: If there is a duplicate
    # False: If there is no duplicate
    def f_checkDuplicate_temp_storage(self, key: str) -> bool:   # Check if a key exists in temporary storage during execution
        if self.temp_storage_during_execution is None:   # Inverse Guard clause: Ensuring that temporary storage is initialized
            return False
        return key in self.temp_storage_during_execution

    def f_get_unique_filename(self, acFileName: str) -> str:   # Appends " (1)", " (2)", etc. before the extension until the name is not a duplicate
        if self.temp_storage_during_execution is None:
            self.temp_storage_during_execution = {}

        if not self.f_checkDuplicate_temp_storage(acFileName):   # Coming from when there is no duplicate
            self.temp_storage_during_execution[acFileName] = None
            return acFileName

        pPath = Path(acFileName)
        acStem, acSuffix = pPath.stem, pPath.suffix
        iCounter = 1
        while True:
            acCandidate = f"{acStem} ({iCounter}){acSuffix}"
            if not self.f_checkDuplicate_temp_storage(acCandidate):
                self.temp_storage_during_execution[acCandidate] = None
                return acCandidate
            iCounter += 1

    def f_remove_from_temp_storage(self, acFileName: str) -> None:   # keeps the duplicate-name cache in sync with a deletion
        if self.temp_storage_during_execution is not None:
            self.temp_storage_during_execution.pop(acFileName, None)