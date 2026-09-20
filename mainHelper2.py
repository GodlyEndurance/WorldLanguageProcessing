'''
mainHelper2.py

Author: Trinh Pham

This file contains additional helper functions for the main executable 2 script.

'''
from pathlib import Path
import re

from OCR.OCR import c_DeepSeekOCR
from WordBracketer import c_WordBracketer

OUTPUT_FILES_DIR = Path(__file__).parent / "OCR_llm_output files"
VOCAB_PROCESSING_DIR = Path(__file__).parent / "Bracketing" / "B_Bracketing Medium Files"        # in-progress vocab lists, not yet fully bracketed
VOCAB_FILES_DIR = Path(__file__).parent / "Bracketing" / "B_IntermediaryBracket ouput files"     # final lists, filtered down to only bracketed words
VOCAB_EXAMPLES_DIR = Path(__file__).parent / "WorldLanguage output files"        # markdown [word | sentence] tables, auto-aligned by any Markdown renderer


# Facade pattern for main2 functions
class c_MainHelper2:
    
    def __init__(self) -> None:
        pass

    # Operations: 
    # 1. f_run: Drives the full pipeline for selecting, bracketing, filtering, and building vocab tables.
    # 2. f_bracketRun: Handles the interactive bracketing of a vocab file.
    # 3. f_bracketFilter: Filters a bracketed vocab file to produce the final word list.
    # 4. f_saveCorrespondExample: Saves the correspondence between words and example sentences.
    # 5. f_buildVocabTable: Builds the final Markdown table for the vocab list.

     # ==================== PUBLIC INTERFACE FOR THE USER ====================

    # Drives the full main2.py pipeline: select/build a vocab file, bracket it interactively,
    # filter down to the bracketed words, correspond each word with an example sentence, and build the final Markdown example table.
    def f_run(self) -> None:
        try:
            # select file
            fpFilePath = self.f_selectFile()
            if fpFilePath is None:
                print("No file selected. Exiting.")
                return

            # run bracket program
            self.f_bracketRun(fpFilePath)

            fpFilteredFile = self.f_bracketFilter(fpFilePath)

            # bind examples with the filtered word list
            fpCorrespondFile = self.f_saveCorrespondExample(fpFilePath, fpFilteredFile)
            print(f"Saved the word/example correspondence to {fpCorrespondFile}")

            # build the final Markdown example table
            fpMarkdownFile = self.f_buildVocabTable(fpFilteredFile)
            print(f"Saved the word/sentence table to {fpMarkdownFile}")
        except KeyboardInterrupt:
            print("\nInterrupted. Exiting.")
        except OSError as e:   # missing/unreadable files or directories (FileNotFoundError is a subclass of OSError)
            print(f"A file error occurred, exiting: {e}")
        except Exception as e:   # last resort: never let an unexpected error crash the CLI with a raw traceback
            print(f"An unexpected error occurred, exiting: {e!r}")

        print("Exiting program...")

    # Input: B_Bracketing Medium Files file
    # Output B_IntermediaryBracket file
    # Will call the Bracket class to perform the bracketing operations
    def f_bracketRun(self, fpFileName: Path) -> None:
        # Implement the logic for bracketing a list of text
        pBracketer = c_WordBracketer(fpFileName)

        print(f"\nEditing {fpFileName.name}. Type a word/phrase, or the line number it's on, to toggle brackets "
              "around all instances of it (bracket if plain, unbracket if already bracketed), 'undo' to undo the "
              "last change, or 'quit' to stop.\n")

        self.f_bracketInputLoop(pBracketer)
        print("Done. Please wait while the changes are being saved into the World Language output files.")

    # Input: a bracketed B_Bracketing Medium Files file
    # Output: the final word list (brackets stripped), saved into "B_IntermediaryBracket ouput files"
    def f_bracketFilter(self, fpFilePath: Path) -> Path:
        aFilteredWords = []
        for acLine in fpFilePath.read_text(encoding="utf-8").splitlines():
            aFilteredWords.extend(re.findall(r"\[([^\[\]]+)\]", acLine))   # pull out every bracketed span, even partial ones like "落[として]"

        VOCAB_FILES_DIR.mkdir(parents=True, exist_ok=True)
        fpFilteredFile = VOCAB_FILES_DIR / fpFilePath.name
        fpFilteredFile.write_text("\n".join(aFilteredWords), encoding="utf-8")
        return fpFilteredFile

    # Will look within the B_Bracketing Medium Files directory for available files
    # Interactive function for either (1) using Deepseek to build a vocab list from the Dialogue section, or (2) selecting a respective Deepseek output file.
    def f_selectFile(self) -> Path | None:
        acChoice = input("Build a new vocab list with DeepSeek, or bracket an existing one? [new/existing]: ").strip().lower()

        match acChoice:
            case "new" | "n":
                print("Building a new vocab list...")
                return self.f_listFiles("new")
            case "existing" | "e":
                print("Selecting an existing vocab list...")
                return self.f_listFiles("existing")
            case _:     # default syntax for the switch statement in Python 3.10+
                print("Invalid choice. Please enter 'new' or 'existing'.")
                return self.f_selectFile()  # recursively prompt again

    # Uses Deepseek to find corresponding examples for the associated words from the input file, using the particular examples from the OCR_llm_output files within the Dialogue section
    # Input: the word list (B_IntermediaryBracket file content) and the source dialogue text to search for examples in
    # Output: each word paired with its corresponding example sentence(s), one "word: sentence" line per input word
    def f_correspondExample(self, acWordListText: str, acDialogueText: str) -> str:
        if not acWordListText.strip():
            return acWordListText

        pDeepSeek = c_DeepSeekOCR()
        if pDeepSeek.pClient is None:
            print("DEEPSEEK_API_KEY not set; skipping example-correspondence step")
            return acWordListText

        try:
            pResponse = pDeepSeek.pClient.chat.completions.create(
                model=pDeepSeek.DEEPSEEK_MODEL,
                messages=[
                    {"role": "system", "content": pDeepSeek.f_load_prompt("correspond_example_prompt.txt")},
                    {"role": "user", "content": f"Words:\n{acWordListText}\n\nDialogue to find examples in:\n{acDialogueText}"},
                ],
                max_tokens=10000,
            )
            acChoice = pResponse.choices[0]
            if not acChoice.message.content:   # empty/None content isn't an exception, so it needs its own diagnostic
                print(f"DeepSeek returned no content (finish_reason={acChoice.finish_reason}, usage={pResponse.usage}); returning word list unchanged")
                return acWordListText
            if acChoice.finish_reason == "length":   # output got cut off mid-way by max_tokens
                print(f"DeepSeek output was truncated by max_tokens (usage={pResponse.usage})")
            return acChoice.message.content
        except Exception as e:
            print(f"DeepSeek example-correspondence failed, returning word list unchanged: {e!r}")
            return acWordListText

    # Builds a real Markdown [word | sentence] table from fpVocabFile's words and saves it into "WorldLanguage output files"
    def f_buildVocabTable(self, fpVocabFile: Path) -> Path:
        fpSourceFile = OUTPUT_FILES_DIR / fpVocabFile.name.removeprefix("Vocab_")
        aSentences = self.f_extract_dialogue_sentences(fpSourceFile.read_text(encoding="utf-8")) if fpSourceFile.exists() else []
        aRows = self.f_buildVocabRows(fpVocabFile, aSentences)

        aLines = ["| Word | Sentence |", "| --- | --- |"]
        for acWord, acSentence in aRows:
            aLines.append(f"| {self.f_escapeCell(acWord)} | {self.f_escapeCell(acSentence)} |")

        VOCAB_EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        fpMarkdownFile = VOCAB_EXAMPLES_DIR / f"{fpVocabFile.stem}.md"
        fpMarkdownFile.write_text("\n".join(aLines), encoding="utf-8")
        return fpMarkdownFile




    # ==================== PRIVATE INTERFACE FOR THE SYSTEM ====================

    def f_listFiles(self, acChoice: str) -> Path | None:
        # Implement the logic for listing files based on the choice
        if acChoice == "new":
            # List files for the "new" choice
            print("Listing files to build a new vocab list...")

            aFiles = sorted(OUTPUT_FILES_DIR.glob("*.txt"), reverse=True)
            if not aFiles:
                print(f"No .txt files found in {OUTPUT_FILES_DIR}")
                return None

            print("Select a file to build a vocab list from:")
            for i, fpFile in enumerate(aFiles, start=1):
                print(f"  {i}. {fpFile.name}")
        
            while True:
                acChoice = input("Enter a number: ").strip()
                if acChoice.isdigit() and 1 <= int(acChoice) <= len(aFiles):
                    return self.f_build_vocab_file(fpSourceFile=aFiles[int(acChoice) - 1])
                print("Invalid choice, try again.")

        elif acChoice == "existing":
            # List files for the "existing" choice
            print("Listing files for selecting an existing vocab list...")

            aFiles = sorted(VOCAB_PROCESSING_DIR.glob("*.txt"), reverse=True) if VOCAB_PROCESSING_DIR.exists() else []
            if not aFiles:
                print(f"No .txt files found in {VOCAB_PROCESSING_DIR}")
                return None

            print("Select an existing vocab file to bracket:")
            for i, fpFile in enumerate(aFiles, start=1):
                print(f"  {i}. {fpFile.name}")
        
            while True:
                acChoice = input("Enter a number: ").strip()
                if acChoice.isdigit() and 1 <= int(acChoice) <= len(aFiles):
                    return aFiles[int(acChoice) - 1]
                print("Invalid choice, try again.")

        else:
            print("Invalid choice. Please enter 'new' or 'existing'. Use the f_selectFile method as the intended entry point.\n")
        

    def f_build_vocab_file(self, fpSourceFile: Path) -> Path:
            # Implement the logic for building a vocab file from the given file
            print(f"Building vocab file from {fpSourceFile}...")

            VOCAB_PROCESSING_DIR.mkdir(parents=True, exist_ok=True)
            fpVocabFile = VOCAB_PROCESSING_DIR / f"Vocab_{fpSourceFile.name}"
            if fpVocabFile.exists():   # don't silently clobber existing bracket progress / shift line numbers on a re-run
                acChoice = input(f"{fpVocabFile.name} already exists. Rebuild it with DeepSeek and lose its bracket progress? [y/N]: ").strip().lower()
                if acChoice not in ("y", "yes"):
                    return fpVocabFile
        
            acOrganizedText = fpSourceFile.read_text(encoding="utf-8")
            acSplitText = c_DeepSeekOCR().f_split_dialogue_words(acOrganizedText)
        
            aWords = []
            aSeenWords = set()
            for acLine in acSplitText.splitlines():
                acStripped = acLine.strip()
                if not acStripped.startswith("- "):   # only the word-list lines DeepSeek adds beneath each sentence, not the sentence/scene-header lines
                    continue
                acWord = acStripped[2:].strip()
                if acWord and acWord not in aSeenWords:   # dedupe while preserving the first-seen form and order
                    aSeenWords.add(acWord)
                    aWords.append(acWord)
        
            VOCAB_PROCESSING_DIR.mkdir(parents=True, exist_ok=True)
            fpVocabFile.write_text("\n".join(aWords), encoding="utf-8")
            return fpVocabFile

    def f_resolve_target_word(self, pBracketer: c_WordBracketer, acRaw: str) -> tuple[str, bool] | None:   # resolves a typed word, or a line number shortcut, to (bare word, was already bracketed)
        acWord = acRaw
        if acRaw.isdigit():   # lazy shortcut: type the file's line number instead of the word itself
            aLines = pBracketer.acText.splitlines()
            iLineIndex = int(acRaw) - 1
            if not (0 <= iLineIndex < len(aLines)):
                print(f"Line {acRaw} is out of range (file has {len(aLines)} lines).")
                return None
            acWord = aLines[iLineIndex].strip()

        bWasBracketed = acWord.startswith("[") and acWord.endswith("]")
        if bWasBracketed:
            acWord = acWord[1:-1]
        return acWord, bWasBracketed

    def f_bracketInputLoop(self, pBracketer: c_WordBracketer) -> None:   # reads bracket/unbracket/undo/quit commands until the user quits
        while True:
            acInput = input("> ").strip()
            if not acInput:
                continue

            acLower = acInput.lower()
            if acLower in ("quit", "exit", "q"):
                return
            elif acLower == "undo":
                print("Undid the last change." if pBracketer.f_undo() else "Nothing to undo.")
            elif acLower.startswith("unbracket "):
                pResolved = self.f_resolve_target_word(pBracketer, acInput[len("unbracket "):].strip())
                if pResolved is None:
                    continue
                acWord, _ = pResolved
                iCount = pBracketer.f_unwrap_word(acWord)
                if iCount:
                    print(f"Unbracketed {iCount} instance(s) of {acWord!r}.")
                else:
                    print(f"No bracketed instances of {acWord!r} found.")
            else:
                pResolved = self.f_resolve_target_word(pBracketer, acInput)
                if pResolved is None:
                    continue
                acWord, bWasBracketed = pResolved

                if bWasBracketed:   # toggle: already bracketed, so this input means "undo that" instead of a no-op wrap attempt
                    iCount = pBracketer.f_unwrap_word(acWord)
                    acVerb = "Unbracketed"
                else:
                    iCount = pBracketer.f_wrap_word(acWord)
                    acVerb = "Wrapped"

                if iCount:
                    print(f"{acVerb} {iCount} instance(s) of {acWord!r}.")
                else:
                    print(f"No instances of {acWord!r} found.")

    def f_extract_dialogue_sentences(self, acOrganizedText: str) -> list[str]:   # pulls the plain sentence lines out of an organized output file's DIALOGUE section
        pMatch = re.search(r"=== DIALOGUE ===\n(.*?)(?=\n=== \w+ ===|\Z)", acOrganizedText, re.DOTALL)
        if pMatch is None:
            return []

        aSentences = []
        for acLine in pMatch.group(1).splitlines():
            acStripped = acLine.strip()
            if acStripped and not (acStripped.startswith("**") and acStripped.endswith("**")):   # skip blank lines and scene headers
                aSentences.append(acStripped)
        return aSentences

    def f_saveCorrespondExample(self, fpFilePath: Path, fpFilteredFile: Path) -> Path:   # looks up fpFilePath's source dialogue text, runs f_correspondExample against it, and saves the result
        fpSourceFile = OUTPUT_FILES_DIR / fpFilePath.name.removeprefix("Vocab_")
        aSentences = self.f_extract_dialogue_sentences(fpSourceFile.read_text(encoding="utf-8")) if fpSourceFile.exists() else []
        acDialogueText = "\n".join(aSentences)

        acCorrespondedText = self.f_correspondExample(fpFilteredFile.read_text(encoding="utf-8"), acDialogueText)

        VOCAB_EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
        fpCorrespondFile = VOCAB_EXAMPLES_DIR / f"{fpFilteredFile.stem}_correspond.txt"
        fpCorrespondFile.write_text(acCorrespondedText, encoding="utf-8")
        return fpCorrespondFile

    def f_buildVocabRows(self, fpVocabFile: Path, aSentences: list[str]) -> list[tuple[str, str]]:   # pairs each vocab word with its bolded example sentence(s)
        aRows = []
        for acRawWord in fpVocabFile.read_text(encoding="utf-8").splitlines():
            acWord = acRawWord.strip()
            if not acWord:
                continue
            acBracketedSpans = re.findall(r"\[([^\[\]]+)\]", acWord)   # handles both fully-wrapped "[word]" and partial "落[として]" leftovers
            if acBracketedSpans:
                acWord = acBracketedSpans[0]

            aMatches = []
            aSeenSentences = set()
            for acSentence in aSentences:   # collect every distinct sentence the word occurs in, in original order
                if acWord in acSentence and acSentence not in aSeenSentences:
                    aSeenSentences.add(acSentence)
                    aMatches.append(acSentence.replace(acWord, f"**{acWord}**"))   # bold the word's occurrences within its own example sentence

            aRows.append((acWord, "; ".join(aMatches)))
        return aRows

    def f_escapeCell(self, acText: str) -> str:   # a literal '|' would break a Markdown table cell
        return acText.replace("|", "\\|")