import argparse
import logging
import time
from pathlib import Path

from globalvars import EXAMPLES
import data_processing as dp
import analysis_lib as al
import fit_analysis as fa
import save_lib as sv

def check_arg(testbool, errtype, logger, errtext=None):
    if not testbool:
        if logger: logger.error(errtext)
        raise errtype(errtext)

def main():
    parser = argparse.ArgumentParser(description="Characterize data from multiple channels with various analyses and fit tests.")
    parser.add_argument('-save','-s', help="Saves results files instead of printing to terminal", action="store_false")
    parser.add_argument('-example','-e', type = int, choices=[0,1,2], help="Runs an example to test that the code runs and is installed correctly.", default = -1)
    # TODO: Update parent_dir (& EXAMPLES) default once I have assets structure
    parser.add_argument('-parent_dir','-p', type=str, help="Parent directory containing RAW subdirectory with channel data files.",default='')
    parser.add_argument('-n_channels','-n', type=int, help="Number of channels to analyze. If empty, analyze all channels available.",default=None)
    parser.add_argument('-outfolder','-o', type=str, default=None, help="Folder name to send logging and results files, or None to not save results and disable logging (default: f'{parent_dir}_results').")
    parser.add_argument('-scope', type=str, choices=['Individual', 'Aggregate', 'Both'], default='Both', help="Scope of analysis: 'Individual', 'Aggregate', or 'Both' (default: 'Both').")
    # parser.add_argument('--analyses', nargs='+', default=None, help="List of non-fitting, non-standard analyses to perform by name (default: None).")
    parser.add_argument('-fits', nargs='+', default=['Langauss', 'EMG'], help="List of fit analyses to perform by name (default: ['Langauss', 'EMG']).")
    parser.add_argument('-fit_tests', nargs='+', choices=['KS', 'chi2', 'chi2/ndof'], default=['chi2/ndof'], help="List of fit tests to perform (default: ['chi2/ndof']).")
    parser.add_argument('-log', type=tuple, default=(), help="Tuple containing file path for logging output and logging level respectively (default: ()). NOTE: If name is dt, output is unix timestamp")
    args = parser.parse_args()

    # Initialization
    if args.example in [0,1,2]:
        ## Ignore everything else and use example data and preset settings
        save, parent_dir, n_channels, scope, fits, fit_tests = EXAMPLES[args.example]
        outfolder = Path('characterization_example')
        outfolder.mkdir(parents=True, exist_ok=True)
        logger = logging.getLogger(__name__)
        logging.basicConfig(filename=outfolder / (str(int(time.time()))+'.log'), encoding='utf-8', level='INFO')
    else:
        ## Use User Input
        parent_dir = args.parent_dir
        outfolder = Path(args.outfolder) if args.outfolder else Path(f'{parent_dir}_results')
        outfolder.mkdir(parents=True, exist_ok=True)
        n_channels, scope = args.n_channels, args.scope
        fits, fit_tests = args.fits, args.fit_tests
        ### Set up logging
        if len(args.log>0):
            if len(args.log)!=2: raise ValueError(f"--log argument must be tuple of length 0 or 2, not {len(args.log)}")
            if (not isinstance(args.log[0],str)) or (not isinstance(args.log[1],str)): raise ValueError(f"--log argument must be tuple of strings")
            logger = logging.getLogger(__name__)
            levels = {
                'DEBUG': logging.DEBUG,
                'INFO': logging.INFO,
                'WARNING': logging.WARNING,
                'ERROR': logging.ERROR,
                'CRITICAL': logging.CRITICAL,
            }
            if args.log[0] == 'dt':
                log_outfile = outfolder / str(int(time.time()))
            else:
                log_outfile = outfolder / args.log[0]
            logging.basicConfig(filename=log_outfile, encoding='utf-8', level=levels[args.log[1]])
        else:
            logger = None

    # Validation and Error Handling
    check_arg(Path(parent_dir).is_dir(), ValueError, logger, errtext=f"Parent directory does not exist: {parent_dir}")

    # for i_ana in analyses:
    #     check_arg(i_ana in al.ana_lib.keys(), ValueError, logger, errtext=f"Analysis config does not exist: {analyses}") 

    for i_fit in fits:
        check_arg(i_fit in al.fit_lib.keys(), ValueError, logger, errtext=f"Fit config does not exist: {i_fit}") 

    for i_test in fit_tests:
        check_arg(i_test in al.fit_test_lib.keys(), ValueError, logger, errtext=f"Fit test config does not exist: {i_test}") 
        
    # Get names of all valid root files from pdir FNAME='DataR_CH0@DT5751_1616_test_14.root'
    pdir_fpaths = [] 
    pdir_raw = Path(parent_dir) / "RAW"
    for ch in range(n_channels):
        token = f'DataR_CH{ch}@DT5751_1616'
        matching_files = [f for f in pdir_raw.iterdir() if f.is_file() and token in f.name]
        if len(matching_files) != 1:
            if len(matching_files) > 1: errtext = f'More than one file with {token} in its name found in {pdir_raw}'
            else: errtext = f"User requested characterization of {n_channels} channels, but no file in {pdir_raw} contains {token} in its name"
            if logger: logger.error(errtext)
            raise FileExistsError(errtext)
        fpath = matching_files[0]
        if fpath.is_file():
            pdir_fpaths.append(fpath)
        else:
            errtext = f"User requested characterization of {n_channels} channels, but {fpath.resolve()} does not exist"
            if logger: logger.error(errtext)
            raise FileExistsError(errtext)

    # Make data structure
    ch_data, agg_data = [], dp.Data()
    for fname in pdir_fpaths:
        ch_data+=[dp.Data()]
        ch_data[-1].load_file(fname)
    for i in range(len(ch_data)): agg_data += ch_data[i]

    data_to_analyze = []
    if scope != 'Aggregate': 
        for data in ch_data: data_to_analyze.append(data)
    if scope != 'Individual': 
        data_to_analyze.append(agg_data)

    # Analyze It
    ## Standard Analysis
    ### Base Analysis
    out_str = '\n                                            Base  Statistics                                            \n'
    out_str +=  '========================================================================================================\n'
    out_str +=  '    Channel   |   Number of Events   |   Duration   |        Event Rate        |   Energy Overflows     \n'
    out_str +=  '  ------------+----------------------+--------------+--------------------------+----------------------  \n'

    base = [['Channel', 'Number of Events', 'Duration', 'Event Rate', 'Energy Overflows'],]
    for data in data_to_analyze: 
        out_str += (str(data) + '\n')
        base.append([str(data.channel), str(data.NEvents), f'{data.duration:.2f}', str(data.event_rate), str(data.Eoverflows)])

    if not save:
        print(out_str)
    if logger:
        logger.info(out_str)

    ### Other Analyses   

    ## Fitting Analysis
    results = {}
    for fit in fits:
        fit_results = []
        data_type =  al.fit_lib[fit]['data_type']
        for dataset in data_to_analyze:
            data = dataset.db[data_type]
            fit_results.append(fa.FitResult(data=data, ana_name=fit, ch=dataset.channel, fit_tests=fit_tests, logger=logger, save=save))
        results[fit] = fit_results

    # Save all the stuff to output folder if requested
    if save: sv.save_to_folder(outfolder, parent_dir.name, base, results, logger=logger)


if __name__ == "__main__":
   main()
