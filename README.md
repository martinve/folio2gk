# Folio2GK

A toolkit to convert hand-crafted first-order-logic clauses in FOLIO dataset (dataset: https://huggingface.co/datasets/tasksource/folio, paper: https://arxiv.org/abs/2209.00840) to simplified clauses that can be processes by GKC reasoner.

### Installation

Install the requirements by running `pip install -r requirements txt`

Aditionally, to parse the simplified clauses the following variables must be set in `converter.py`
- `GKC_CMD` - command to be called for GKC executable
- `TEMP_FILE_NAME` (default `tmpfile.txt`) - cache file for GKC to use for clause conversion

### Running the Software

- Convering clauses to simplified format: `./converter.py > clauses.txt`
- Converting simplified format to JSON-LD-LOGIC: `./converter.py --json > clauses.txt`. 

Additionally it is possilbe to limit the number of tests to be processed by `--max N` parameter, e.g `./converter.py --max 1 --json`

### Converted clauses

Already converted clauses can be found in `clauses.txt`

### Files

* `ttfilter.py` 


# FIX Patterns

t2-49: conclusion-FOL needs extra ( at POS2