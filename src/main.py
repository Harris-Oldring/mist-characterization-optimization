import argparse
import logging
import os

from globalvars import PARENT_DIR
import data_processing as dp
import analysis_lib as al
import plot_lib as pl

def check_arg(arg, testbool, errtype, errtext=None):
    if not testbool: # Ensure parent directory exists
        self.logger.error(errtext)
        raise errtype(errtext)

def main():
    parser = argparse.ArgumentParser(description="Characterize data from multiple channels with various analyses and fit tests.")
    parser.add_argument('-e','example', help="Runs an example to test that the code runs and is installed correctly.",action="store_true")
    parser.add_argument('-p','parent_dir', type=str, help="Parent directory containing RAW subdirectory with channel data files.",default=PARENT_DIR)
    parser.add_argument('-n','n_channels', type=int, help="Number of channels to analyze. If empty, analyze all channels available.",default=None)
    parser.add_argument('--scope', type=str, choices=['individual', 'aggregate', 'both'], default='both', help="Scope of analysis: 'individual', 'aggregate', or 'both' (default: 'both').")
    parser.add_argument('--general_analyses', nargs='+', default=['Number of Events', 'Sample Duration', 'Average Event Rate', 'Average Baseline'], help="List of general analyses to perform by name (default: ['Number of Events', 'Sample Duration', 'Average Event Rate', 'Average Baseline']).")
    parser.add_argument('--fit_analyses', nargs='+', default=['Langauss Height', 'Exponentially Modified Gaussian Energy'], help="List of fit analyses to perform by name (default: ['Langauss Height', 'Exponentially Modified Gaussian Energy']).")
    parser.add_argument('--fit_tests', nargs='+', choices=['kolmogorov_smirnov', 'anderson_darling', 'chi_squared', 'chi_squared_per_ndof'], default=['chi_squared_per_ndof'], help="List of fit tests to perform (default: ['chi_squared_per_ndof']).")
    parser.add_argument('-o','--outfile', type=str, default=None, help="File path to save results as a CSV, or None to not save results (default: None).")
    parser.add_argument('--mode', type=str, choices=['w', 'a'], default='w', help="File mode for saving results: 'w' for write (overwrite) or 'a' for append (default: 'w').")
    parser.add_argument('--plots', type=str, default=None, help="File path to save plots as a PDF. If plots and save is specified, plots are saved to the specified PDF file. If plots is specified but save is None, plots are displayed, but not saved to a file. Currently no support for appending to pdf. (default: None).")
    parser.add_argument('--log', type=str, default='characterization.log', help="File path for logging output (default: 'characterization.log').") #make this date/timeso it doesnt overwrtite itself or some such
    parser.add_argument('--no_clean_up', action='store_true', help="Whether to not clean up intermediate files after saving results.")
    args = parser.parse_args()

    if args.example:
        print("Ignore everything else and use example data and preset settings")
    else:

        ## Validation and Error Handling
        check_arg(args.parent_dir, os.path.isdir(args.parent_dir), ValueError, errtext=f"Parent directory does not exist: {args.parent_dir}")

        for i_ana in args.fit_analyses:
            check_arg(i_ana, args.fit_analysis in al.lib.keys(), ValueError, errtext=f"Analysis config does not exist: {args.parent_dir}") 

        for i_test in args.fit_tests:
            check_arg(i_test, i_test in ['kolmogorov_smirnov', 'anderson_darling', 'chi_squared', 'chi_squared_per_ndof'], ValueError, errtext=f"Analysis config does not exist: {args.parent_dir}") 
        
        pdir_fnames=[] #get names of all valid root files from pdir FNAME='DataR_CH0@DT5751_1616_test_14.root'
        #also bool something about channel choices - like only doing ch 1 data, probably based on file name format

        # for every valid fname, make a Data object with all of that file's data.
        ch_data=[]
        for fname in pdir_fnames:
            ch_data+=[dp.Data()]
            ch_data[-1].load_file(fname)

        usrconfig={
            'outfile'=args.outfile,
            'fit_analyses'=args.fit_analyses,
            ''
        } 

        #which analyses?
        #check if userchoice is in analysis config dict - if so, use that. otherwise error msg and exit

        #do that. save all info associated, maybe as dict

        #plot them

        #save them (ominous)

if __name__ == "__main__":
   main()
