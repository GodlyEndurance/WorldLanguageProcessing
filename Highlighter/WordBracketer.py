
'''
WordBracketer.py

Author: Trinh Pham

Wraps every instance of a given word/phrase in a text file with brackets ([]).
Useful for Japanese text, which isn't spaced per-word, so bolding alone can't
highlight a run of consecutive words the way it can in spaced languages.
'''

import re
from pathlib import Path


class c_WordBracketer:  # tracks a single text file's content in memory, with disk persistence and undo history
    def __init__(self, fpFilePath: Path) -> None:
        self.fpFilePath = fpFilePath
        self.acText = fpFilePath.read_text(encoding="utf-8")
        self.aHistory: list[str] = []   # snapshots of acText taken before each successful wrap, for undo

    def f_wrap_word(self, acWord: str) -> int:   # wraps all not-yet-bracketed instances of acWord, saves to disk, returns the count wrapped
        pPattern = re.compile(r"(?<!\[)" + re.escape(acWord) + r"(?!\])")
        acNewText, iCount = pPattern.subn(f"[{acWord}]", self.acText)

        if iCount == 0:
            return 0

        self.aHistory.append(self.acText)
        self.acText = acNewText
        self.f_save()
        return iCount

    def f_undo(self) -> bool:   # restores the text to before the last wrap; returns False if there's nothing to undo
        if not self.aHistory:
            return False

        self.acText = self.aHistory.pop()
        self.f_save()
        return True

    def f_unwrap_word(self, acWord: str) -> int:   # removes the brackets from all bracketed instances of acWord, saves to disk, returns the count unwrapped
        acBracketed = f"[{acWord}]"
        iCount = self.acText.count(acBracketed)

        if iCount == 0:
            return 0

        self.aHistory.append(self.acText)
        self.acText = self.acText.replace(acBracketed, acWord)
        self.f_save()
        return iCount

    def f_save(self) -> None:
        self.fpFilePath.write_text(self.acText, encoding="utf-8")
