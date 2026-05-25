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
for (( n=START; n<STOP; n++ )); do
   PARENT_DIR="${TARGET_DIR}/test_${n}"
   RAW_DIR="${PARENT_DIR}/RAW"
    
   ## Check if the RAW directory exists
   if [ ! -d "$RAW_DIR" ]; then
      echo "Warning: Directory '$RAW_DIR' does not exist. Skipping test_${n}."
      continue
   fi
    
   ## Determine n_channels by counting files containing 'CH'
   ### 'find' is used here to safely count files only (ignoring subdirectories) even if names have spaces
   N_CHANNELS=$(find "$RAW_DIR" -maxdepth 1 -type f -name "*CH*" | wc -l)
    
   ## Check for zero channels
   if [ "$N_CHANNELS" -eq 0 ]; then
      echo "Warning: No files containing 'CH' found in '$RAW_DIR'. Skipping test_${n}."
      continue
   fi
    
   ## Execute the Python script
   echo "Processing test_${n} with ${N_CHANNELS} channels..."
   if [ $n -eq $START ]; then
      # echo "Write mode" # DEBUG
      python3 "$PY_SCRIPT" "$PARENT_DIR" "$N_CHANNELS" --save "$SUMMARY_FILE" --mode w --no_clean_up
   elif [ $n -eq $END ]; then
      # echo "Append mode with clean up for last test" # DEBUG
      python3 "$PY_SCRIPT" "$PARENT_DIR" "$N_CHANNELS" --save "$SUMMARY_FILE" --mode a 
   else
      # echo "Append mode with no clean up for intermediate tests" # DEBUG
      python3 "$PY_SCRIPT" "$PARENT_DIR" "$N_CHANNELS" --save "$SUMMARY_FILE" --mode a --no_clean_up 
   fi
    
   ## Check if the python script failed and warn the user
   if [ $? -ne 0 ]; then
      echo "Warning: characterization3.py returned an error for test_${n}."
   fi
done

echo ""
echo "======================================================"
echo "Run complete!"