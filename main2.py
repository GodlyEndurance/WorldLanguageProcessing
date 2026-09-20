
'''
main2.py

Author: Trinh Pham

Interactive CLI for bracketing words in a vocab list built from an "OCR_llm_output files" text file.
This is a second, separate entry point from main.py. It does not do DB work. All the actual
logic (choosing/building the vocab file, running the interactive bracketer, filtering the
bracketed words, and building the Markdown example table) lives in mainHelper2.c_MainHelper2.
This file is the CLI entry point without needing to know anything under the hood.
'''

from mainHelper2 import c_MainHelper2   # Done as a class, to group all the helper functions and state together


# The input is interactive, so there isn't any other code needed beyond this CLI entry point.
def main() -> None:
    h2 = c_MainHelper2()    # LLM is hardcoded to Deepseek
    h2.f_run()


if __name__ == "__main__":
    main()


