
'''
main2.py

Author: Trinh Pham

Interactive CLI for bracketing words in a vocab list built from an "output files" text file.
This is a second, separate entry point from main.py. It does not do DB work, but it does use
DeepSeek (via c_DeepSeekOCR) to split each DIALOGUE sentence into its individual words, dedupe
them (keeping the first occurrence of each), and write the result into the "VocabProcessing files"
folder. Once bracketing is done, f_bracketFilter() keeps only the bracketed words and saves that
final list into the "vocab files" folder.
'''

from pathlib import Path
import re

try:
    from .OCR.OCR import c_DeepSeekOCR
    from .Highlighter.WordBracketer import c_WordBracketer
except ImportError:
    from OCR.OCR import c_DeepSeekOCR
    from Highlighter.WordBracketer import c_WordBracketer

OUTPUT_FILES_DIR = Path(__file__).parent / "output files"
VOCAB_PROCESSING_DIR = Path(__file__).parent / "VocabProcessing files"   # in-progress vocab lists, not yet fully bracketed
VOCAB_FILES_DIR = Path(__file__).parent / "vocab files"                 # final lists, filtered down to only bracketed words
VOCAB_EXAMPLES_DIR = Path(__file__).parent / "vocabExamples files"       # markdown [word | sentence] tables, auto-aligned by any Markdown renderer


def f_build_vocab_file(fpSourceFile: Path) -> Path:   # splits the source's dialogue into words via DeepSeek, dedupes them, and saves the list to "VocabProcessing files"
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


def f_choose_file() -> Path:   # lists the .txt files in "output files", lets the user pick one, and returns its generated vocab-list file
    aFiles = sorted(OUTPUT_FILES_DIR.glob("*.txt"), reverse=True)
    if not aFiles:
        raise FileNotFoundError(f"No .txt files found in {OUTPUT_FILES_DIR}")

    print("Select a file to build a vocab list from:")
    for i, fpFile in enumerate(aFiles, start=1):
        print(f"  {i}. {fpFile.name}")

    while True:
        acChoice = input("Enter a number: ").strip()
        if acChoice.isdigit() and 1 <= int(acChoice) <= len(aFiles):
            return f_build_vocab_file(aFiles[int(acChoice) - 1])
        print("Invalid choice, try again.")


def f_choose_vocab_file() -> Path:   # lists in-progress files in "VocabProcessing files" and lets the user pick one directly, skipping the DeepSeek step entirely
    aFiles = sorted(VOCAB_PROCESSING_DIR.glob("*.txt"), reverse=True) if VOCAB_PROCESSING_DIR.exists() else []
    if not aFiles:
        raise FileNotFoundError(f"No .txt files found in {VOCAB_PROCESSING_DIR}")

    print("Select an existing vocab file to bracket:")
    for i, fpFile in enumerate(aFiles, start=1):
        print(f"  {i}. {fpFile.name}")

    while True:
        acChoice = input("Enter a number: ").strip()
        if acChoice.isdigit() and 1 <= int(acChoice) <= len(aFiles):
            return aFiles[int(acChoice) - 1]
        print("Invalid choice, try again.")


def f_bracketFilter(fpFilePath: Path) -> Path:   # keeps only the bracketed words from a VocabProcessing file, strips their brackets, and saves the final list to "vocab files"
    aFilteredWords = []
    for acLine in fpFilePath.read_text(encoding="utf-8").splitlines():
        aFilteredWords.extend(re.findall(r"\[([^\[\]]+)\]", acLine))   # pull out every bracketed span, even partial ones like "落[として]"

    VOCAB_FILES_DIR.mkdir(parents=True, exist_ok=True)
    fpFilteredFile = VOCAB_FILES_DIR / fpFilePath.name
    fpFilteredFile.write_text("\n".join(aFilteredWords), encoding="utf-8")
    return fpFilteredFile


def f_extract_dialogue_sentences(acOrganizedText: str) -> list[str]:   # pulls the plain sentence lines out of an organized output file's DIALOGUE section
    pMatch = re.search(r"=== DIALOGUE ===\n(.*?)(?=\n=== \w+ ===|\Z)", acOrganizedText, re.DOTALL)
    if pMatch is None:
        return []

    aSentences = []
    for acLine in pMatch.group(1).splitlines():
        acStripped = acLine.strip()
        if acStripped and not (acStripped.startswith("**") and acStripped.endswith("**")):   # skip blank lines and scene headers
            aSentences.append(acStripped)
    return aSentences


def f_buildVocabTable(fpVocabFile: Path) -> Path:   # builds a real Markdown [word | sentence] table from fpVocabFile's words and saves it into "vocabExamples files"
    fpSourceFile = OUTPUT_FILES_DIR / fpVocabFile.name.removeprefix("Vocab_")
    aSentences = f_extract_dialogue_sentences(fpSourceFile.read_text(encoding="utf-8")) if fpSourceFile.exists() else []

    def f_escape_cell(acText: str) -> str:   # a literal '|' would break a Markdown table cell
        return acText.replace("|", "\\|")

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

    aLines = ["| Word | Sentence |", "| --- | --- |"]
    for acWord, acSentence in aRows:
        aLines.append(f"| {f_escape_cell(acWord)} | {f_escape_cell(acSentence)} |")

    VOCAB_EXAMPLES_DIR.mkdir(parents=True, exist_ok=True)
    fpMarkdownFile = VOCAB_EXAMPLES_DIR / f"{fpVocabFile.stem}.md"
    fpMarkdownFile.write_text("\n".join(aLines), encoding="utf-8")
    return fpMarkdownFile


def f_resolve_target_word(pBracketer: c_WordBracketer, acRaw: str) -> tuple[str, bool] | None:   # resolves a typed word, or a line number shortcut, to (bare word, was already bracketed)
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


def f_run_bracketer(fpFilePath: Path) -> None:   # interactive bracket/unbracket/undo/quit loop for a single file
    pBracketer = c_WordBracketer(fpFilePath)

    print(f"\nEditing {fpFilePath.name}. Type a word/phrase, or the line number it's on, to toggle brackets "
          "around all instances of it (bracket if plain, unbracket if already bracketed), 'undo' to undo the "
          "last change, or 'quit' to stop.\n")

    while True:
        acInput = input("> ").strip()
        if not acInput:
            continue

        acLower = acInput.lower()
        if acLower in ("quit", "exit", "q"):
            break
        elif acLower == "undo":
            print("Undid the last change." if pBracketer.f_undo() else "Nothing to undo.")
        elif acLower.startswith("unbracket "):
            pResolved = f_resolve_target_word(pBracketer, acInput[len("unbracket "):].strip())
            if pResolved is None:
                continue
            acWord, _ = pResolved
            iCount = pBracketer.f_unwrap_word(acWord)
            if iCount:
                print(f"Unbracketed {iCount} instance(s) of {acWord!r}.")
            else:
                print(f"No bracketed instances of {acWord!r} found.")
        else:
            pResolved = f_resolve_target_word(pBracketer, acInput)
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

    print("Done.")



def main() -> None:
    acChoice = input("Build a new vocab list with DeepSeek, or bracket an existing one? [new/existing]: ").strip().lower()
    fpFilePath = f_choose_vocab_file() if acChoice in ("existing", "e") else f_choose_file()
    f_run_bracketer(fpFilePath)

    fpFilteredFile = f_bracketFilter(fpFilePath)
    fpMarkdownFile = f_buildVocabTable(fpFilteredFile)
    print(f"Saved the word/sentence table to {fpMarkdownFile}")

    print("Exiting program...")




if __name__ == "__main__":
    main()
