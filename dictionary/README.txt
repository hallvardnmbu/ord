Sources:
    Words:
    * nob: https://www.nb.no/sprakbanken/ressurskatalog/oai-nb-no-sbr-5/
    * nnb: https://www.nb.no/sprakbanken/ressurskatalog/oai-nb-no-sbr-41/
    Dictionary:
    * https://v1.ordbokene.no/api

Run the files in the following order:
1. `parse.mjs`
2. `detailed.mjs`
3. `duplicates.mjs`
4. `dating.mjs`

Information about the files:
1. `parse.mjs`
    Parses the metadata from the downloaded and generated files.
    See the links above and the `./abbreviations/` folder for more information.
2. `detailed.mjs`
    Extracts detailed information about the words.
3. `duplicates.mjs`
    Finds duplicates in the data and removes them.
4. `dating.mjs`
    Generates a unique date for each word, starting today.
    Used to extract the word of the day for the application.
