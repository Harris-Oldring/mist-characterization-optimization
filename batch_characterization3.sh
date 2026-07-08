#!/bin/bash

# batch_characterization3.py
#
# !! Before you run this for the first time, do chmod +x batch_characterization3.sh in terminal to give the necessary permissions
#
#
# DESCRIPTION:
#   Batch-processing helper for exploratory data characterization. This script
#   iterates over a collection of CoMPASS output directories named test_{n} and
#   computes summary metrics using characterization3.py. 
#
# USAGE:
#   batch_characterization3.sh <target_directory> <start_integer> <stop_integer> [path_to_characterization3]
#
#   target_directory                   : The directory which contains the subdirectories to be iterated over
#   start_integer                      : The index for the first subdirectory 
#                                           ex. 4 => first processed subdirectory is test_4
#   end_integer                        : The index of the last subdirectory (exclusive) 
#                                           ex. 6 => last processed subdirectory is test_5
#   path_to_characterization3 (opt) : If characterization3.py is not in the same directory as 
#                                        batch_characterization3.sh, will need to provide the path 
#                                        to characterization3.py as the 4th argument. 
#
# OUTPUTS:
#   - Per-file summary files (CSV/JSON) containing basic metrics per column.
#   - An aggregate index/summary that lists file-level stats and overall
#     dataset characteristics.
#   - Log file with processing events and any detected warnings (e.g., mixed
#     data types, excessive missingness).
#
# NOTES:
#   - Intended to run characterization3.py on several CoMPASS test results
#   - Will create a single csv/xlsx file containing the results of all tests
#   - This allows the user to conduct experiments to see how certain metrics change in different tests
# 

# Check if the correct number of arguments is provided
if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "Usage: $0 <target_directory> <start_integer> <stop_integer> [path_to_characterization3]"
    echo "Example: $0 /path/to/data 0 10 /path/to/scripts/characterization3.py"
    exit 1
fi

TARGET_DIR="$1"
START="$2"
STOP="$3"
END=$((STOP - 1))

# Determine the directory where this bash script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"

# Set the Python script path: use argument 4 if provided, else default to the script's own directory
PY_SCRIPT="${4:-$SCRIPT_DIR/characterization3.py}"

# Validate target directory
if [ ! -d "$TARGET_DIR" ]; then
   echo "Error: Target directory '$TARGET_DIR' does not exist."
   exit 1 # TODO: Replace this with something that doesn't close the terminal
fi

# Validate that start and stop are integers using regular expressions
if ! [[ "$START" =~ ^-?[0-9]+$ ]] || ! [[ "$STOP" =~ ^-?[0-9]+$ ]]; then
   echo "Error: start_integer and stop_integer must be valid integers."
   exit 1
fi

# Validate the Python script exists
if [ ! -f "$PY_SCRIPT" ]; then
   echo "Error: Python script not found at '$PY_SCRIPT'"
   exit 1
fi

# Define the absolute path for the summary file
SUMMARY_FILE="${TARGET_DIR}/summary"

echo "======================================================"
echo "Starting characterization run"
echo "Target directory : $TARGET_DIR"
echo "Range            : test_$START to test_$((STOP - 1))"
echo "Python script    : $PY_SCRIPT"
echo "Summary file     : $SUMMARY_FILE"
echo "======================================================"
echo ""

# Loop from START (inclusive) to STOP (exclusive)
python3 - <<EOF
import subprocess
import sys
from tqdm import tqdm
import glob

TARGET_DIR = "$TARGET_DIR"
START = $START
STOP = $STOP
END = $END
PY_SCRIPT = "$PY_SCRIPT"
SUMMARY_FILE = "$SUMMARY_FILE"

for n in tqdm(range(START, STOP), desc="Processing tests", unit="test"):
    parent_dir = f"{TARGET_DIR}/test_{n}"
    raw_dir = f"{parent_dir}/RAW"

    # check existence via subprocess-safe method
    import os
    if not os.path.isdir(raw_dir):
        tqdm.write(f"Skipping test_{n} (missing RAW dir)")
        continue

    channels = glob.glob(f"{raw_dir}/*CH*")
    n_channels = len(channels)

    if n_channels == 0:
        tqdm.write(f"Skipping test_{n} (no channels)")
        continue

   #  tqdm.write(f"Running test_{n} with {n_channels} channels")

    if n == START:
        mode = "w"
        extra = ["--no_clean_up"]
    elif n == END:
        mode = "a"
        extra = []
    else:
        mode = "a"
        extra = ["--no_clean_up"]

    cmd = [
        "python3",
        PY_SCRIPT,
        parent_dir,
        str(n_channels),
        "--save",
        SUMMARY_FILE,
        "--mode",
        mode,
        *extra
    ]

    result = subprocess.run(cmd)

    if result.returncode != 0:
        tqdm.write(f"Warning: characterization3.py failed for test_{n}")
EOF

echo ""
echo "======================================================"
echo "Run complete!"