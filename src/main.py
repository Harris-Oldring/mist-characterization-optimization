import argparse
import logging
import os
from pathlib import Path

from globalvars import PARENT_DIR
import data_processing as dp
import analysis_lib as al
import plot_lib as pl

def check_arg(arg, testbool, errtype, logger, errtext=None):
    if not testbool:
        logger.error(errtext)
        raise errtype(errtext)

def main():
    parser = argparse.ArgumentParser(description="Characterize data from multiple channels with various analyses and fit tests.")
    parser.add_argument('-e','example', help="Runs an example to test that the code runs and is installed correctly.",action="store_true")
    parser.add_argument('-p','parent_dir', type=str, help="Parent directory containing RAW subdirectory with channel data files.",default=PARENT_DIR)
    parser.add_argument('-n','n_channels', type=int, help="Number of channels to analyze. If empty, analyze all channels available.",default=None)
    parser.add_argument('--scope', type=str, choices=['Individual', 'Aggregate', 'Both'], default='Both', help="Scope of analysis: 'Individual', 'Aggregate', or 'Both' (default: 'Both').")
    parser.add_argument('--analyses', nargs='+', default=None, help="List of non-fitting, non-standard analyses to perform by name (default: None).")
    parser.add_argument('--fits', nargs='+', default=['Langauss', 'EMG'], help="List of fit analyses to perform by name (default: ['Langauss', 'EMG']).")
    parser.add_argument('--fit_tests', nargs='+', choices=['KS', 'chi2', 'chi2/ndof'], default=['chi2/ndof'], help="List of fit tests to perform (default: ['chi2/ndof']).")
    parser.add_argument('-o','--outfile', type=str, default=None, help="File path to save results as a CSV, or None to not save results (default: None).")
    parser.add_argument('--mode', type=str, choices=['w', 'a'], default='w', help="File mode for saving results: 'w' for write (overwrite) or 'a' for append (default: 'w').")
    parser.add_argument('--plots', type=str, default=None, help="File path to save plots as a PDF. If plots and save is specified, plots are saved to the specified PDF file. If plots is specified but save is None, plots are displayed, but not saved to a file. Currently no support for appending to pdf. (default: None).")
    parser.add_argument('--log', type=str, default='characterization.log', help="File path for logging output (default: 'characterization.log').") #make this date/timeso it doesnt overwrtite itself or some such
    parser.add_argument('--no_clean_up', action='store_true', help="Whether to not clean up intermediate files after saving results.")
    args = parser.parse_args()

    # Set up logging
    logger = logging.getLogger(__name__)
    logging.basicConfig(filename='characterization.log', encoding='utf-8', level=logging.WARNING)

    if args.example:
        print("Ignore everything else and use example data and preset settings")
    else:

        ## Validation and Error Handling
        check_arg(args.parent_dir, Path(args.parent_dir).is_dir(), ValueError, logger, errtext=f"Parent directory does not exist: {args.parent_dir}")

        for i_ana in args.analyses:
            check_arg(i_ana, i_ana in al.ana_lib.keys(), ValueError, logger, errtext=f"Analysis config does not exist: {args.fit_analyses}") 

        for i_fit in args.fits:
            check_arg(i_fit, i_fit in al.fit_lib.keys(), ValueError, logger, errtext=f"Fit config does not exist: {args.fit_analyses}") 

        for i_test in args.fit_tests:
            check_arg(i_test, i_test in al.fit_test_lib.keys(), ValueError, logger, errtext=f"Fit test config does not exist: {args.fit_tests}") 
        
        pdir_fnames=[] #get names of all valid root files from pdir FNAME='DataR_CH0@DT5751_1616_test_14.root'
        pdir_raw = Path(args.parent_dir) / "RAW"
        for ch in range(args.n_channels):
            fname = f'DataR_CH{ch}@DT5751_1616_test_14.root'
            fpath = pdir_raw / fname
            if fpath.is_file():
                pdir_fnames.append(fname)
            else:
                errtext = f"User requested characterization of {args.n_channels} channels, but {fname} does not exist"
                logger.error(errtext)
                raise FileExistsError(errtext)

        #also bool something about channel choices - like only doing ch 1 data, probably based on file name format

        # Make data structures
        ch_data, agg_data = [], dp.Data()
        for fname in pdir_fnames:
            ch_data+=[dp.Data()]
            ch_data[-1].load_file(fname)
        for i in len(ch_data): agg_data += ch_data[i]

        data_to_analyze = []
        if args.scope != 'Aggregate': 
            for data in ch_data: data_to_analyze.append(data)
        if args.scope != 'Individual': 
            data_to_analyze.append(agg_data)

        # Analyze it
        ## Standard Analysis

        ## Fitting Analysis
        for fit in args.fit:
            for data in data_to_analyze:
                perform_analysis


        #which analyses?
        #check if userchoice is in analysis config dict - if so, use that. otherwise error msg and exit

        #do that. save all info associated, maybe as dict

        #plot them

        #save them (ominous)

if __name__ == "__main__":
   main()
