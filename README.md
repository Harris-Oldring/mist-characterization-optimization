# mist-characterization-optimization
Useful scripts, CAEN DT5751 digitizer data, and Jupyter notebooks created while optimizing the P-ONE-D MIST characterization process. 

## Installation
### Prerequisites
* Python>=3.14
* Git

### Setup Instructions
Here are the instructions and requirements for setting up mist-characterization-optimization for yourself (macOS/Linux)

1. **Clone the repository:**
   ```bash
   git clone git@github.com:your-username/your-repo-name.git
   cd your-repo-name
   ```
2. **Create and activate a virtual environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```
3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```
4. **Verify the installation**
   ```bash
   python characterization3.py --help
   ```
5. **Manually update landaupy**
   Change lines 215 and 133 of landau.py and langauss.py, respectively, to replace `np.trapz` with `np.trapezoid` to avoid a warning about the deprecation of `np.trapz` for integration in favor of `np.trapezoid`.

## Overview of Repository Structure
 * `src` : The characterization script and helper scripts
    * `main.py` : The main analysis script
    * `globalvars.py` : Several global variables that need to be declared based on the user's physical setup
    * `save_lib.py` : Helper functions for saving results
    * `fit_analysis.py` : A class which performs fit analyses on data, including fitting, fit tests, and plotting
    * `data_processing.py` : A class which extracts and stores data from CoMPASS output files
    * `analysis_lib.py` : Contains helper functions for analysis, as well as fit and fit-test configuration dictionaries
 * `analysis` : Contains several Jupyter notebooks, which were used to develop the analysis scripts
    * `characterization_development` : Development notebooks for basic characterization techniques
    * `sample_duration` : Used to explore how the sample duration of data affects the uncertainty of various analyses
    * `daq_settings` : Used to explore how the DAQ settings of the CAEN DT5751 digitizer affect the waveform data
    * `efficiency_map` : A study done into how the geometry of the MIST affects the efficiency of the detector
 * `assets` : Sample data
 * `batch_characterization.sh` : A script to perform batch characterization of several run results at once
 * `batch_split_and_characterization.sh` : A bare-bones script to perform batch splitting and characterization of several run results at once
 * `compass_result_splitter.py` : A script to split a CoMPASS run result into synchronized, fixed-duration chunks while preserving the original RAW folder and channel file structure

## Usage
### `src/main.py`
This is the current characterization script, which allows you to perform analysis on data returned by the CAEN DT5751 digitizer using the CoMPASS software with "Acquisition/Save Raw Data" selected. This may be run from the terminal or used as a class. 

### Configuring New Analysis
If you wish to perform fitting that there is not yet been implemented, you will need to add a new entry to the `fit_analysis_dict` in `analysis_lib.py`. This dictionary contains the configuration for each fit analysis, including the function to be used for fitting, the function to be used for testing the fit, and the function to be used for plotting the results. These functions follow a specific structure, which can been seen by examining the existing functions in `fit_analysis.py`. Once you have added your new entry to the `fit_analysis_dict` and updated the argparser in `main.py`, you will be able to use it in the `--fit_analysis` argument of `main.py`. Fit tests can be added in a similar manner, by adding a new entry to the `fit_test_dict` in `analysis_lib.py`. 

The framework for doing other kinds of analysis is not entirely fleshed out yet.

### Help and Examples
Some examples can be run by using the -e flag, aas well as the index of the example you want to run from globalvars.EXAMPLES. For example, to run the first example, you would do:
```bash
python3 src/main.py -e 0
```
You can access help for the arguments of `main.py` by using the -h flag:
```bash
python3 src/main.py -h
```

### `batch_characterization.sh`
Currently deprecated
<span style="opacity: 0.5;">This script is intended to allow for the batch characterization of several run results at once. These run results must each be a CoMPASS output directories named `test_{n}`, which allows `batch_characterization.sh` to iterate between a stop and start run result, given the name of the directory these run results are in. `characterization3.py` is run on each of these run results, and the outputs are collected in a single .xlsx file. `batch_characterization.sh` takes the following form:
```
batch_characterization3.sh <target_directory> <start_integer> <stop_integer> [path_to_characterization3]
```
A description of the arguments is as follows:
 - `target_directory`                   : The directory which contains the subdirectories to be iterated over
 - `start_integer`                      : The index for the first subdirectory\
   &emsp;ex. 4 => first processed subdirectory is test_4
 - `end_integer`                        : The index of the last subdirectory (exclusive)\
   &emsp;ex. 6 => last processed subdirectory is test_5
 - `path_to_characterization3` (opt) : If characterization3.py is not in the same directory as batch_characterization3.sh, will need to provide the path to characterization3.py as the 4th argument.   
</span>

### `compass_result_splitter.py`
This script splits a CoMPASS run result into synchronized, fixed-duration chunks while preserving the original `RAW` folder and channel file structure.

### Running `compass_result_splitter.py` in Terminal
`compass_result_splitter.py` takes the following positional arguments:
 - `parent_dir`: Parent directory containing the `RAW` subdirectory with channel ROOT files.
 - `n_channels`: Number of channels to parse.
 - `duration`: Duration of each chunk in seconds.
Additional optional arguments allow you to control output location and ROOT tree details:
 - `-o, --output-dir`: Target overarching output directory (default: same location as `parent_dir`).
 - `-t, --tree-name`: TTree name inside the ROOT files (default: `Data_R;1`).
 - `--time-unit-factor`: Timestamp units per second. Use `1e12` for picoseconds or `1e9` for nanoseconds (default: `1e12`).
 - `--timestamp-branch`: Timestamp branch name inside the ROOT tree (default: `Timestamp`).

The script writes output in the form:

```
<output_dir>/<parent_dir_name>_<duration>/test_<i>/RAW/CH<channel>.root
```

Each output chunk is generated from the common time windows present in all channels.

### More Examples
To split `settings_experimentation/test_0` into 60-second synchronized chunks using three channels:
```bash
python3 src/compass_result_splitter.py settings_experimentation/test_0 3 60
```
To write the chunked results to a custom output directory:
```bash
python3 src/compass_result_splitter.py settings_experimentation/test_0 3 60 -o split_outputs
```

