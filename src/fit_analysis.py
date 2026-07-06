import numpy as np
import analysis_lib as al
from scipy.interpolate import make_interp_spline
from plot_lib import plot_hist_with_fit

def fit_analysis_(data, ana_name, fit_tests, ch, logger, save = False):
   '''
   Performs the specified fit analysis on the given data based on the scope.
   Fits the appropriate distribution, performs the specified fit tests, generates plots if requested, and compiles results into a structured format for saving or display.
   Parameters:
      data (array-like): The (possibly transformed) data to be analyzed.
      fit_analysis (dict): The fit analysis configuration dict from fit_analyses_config.
      scope (str): The scope of analysis ('individual' or 'aggregate').
      channel (int, optional): The channel number for individual analyses; None for aggregate analyses.
   Returns:
      None (results are printed and/or saved based on user configuration)
   '''
   ana = al.fit_lib[f'{ana_name}']
   output_line = f"Analysis: {ana['name']}, Channel: {ch if ch is not None else 'all'}"

   ### Compile results into a structured format for saving or display, including fit parameters and overflow information.
   result_row = {
      'Channel': ch if ch is not None else 'all',
      }

   ### Fit distribution
   params, param_errs = ana['fit_func'](data)
   param_dict = dict(zip(ana['params'], params))
   param_err_dict = dict(zip(f'{ana['params']} Error', param_errs))
   result_row.update(param_dict, param_err_dict)
        
   ### Display output if not saving to file
   if not save:
      print(output_line)
      for _ in range(len(output_line)): print('=', end='')
      print(f"\n{ana['fit_type']} fit results:")
      for _ in range(len(ana['fit_type']) + 13): print('-', end='')
      print()
      for param in param_dict:
         for i in range(len(params)): print(f'{ana['params'][i]:^13}', end=' |')
         for i in range(len(params)): print('----------+')
         for i in range(len(params)): print(f'  {params[i]:>11.2f}', end=' |')
         for i in range(len(params)): print(f'± {params[i]:>11.2f}', end=' |')
      print()
   else:
      logger.info(output_line)

   ### Generate fit CDF and plots
   x = np.linspace(np.min(data), np.max(data), 2000)
   y = ana['pdf_func'](x, params)
   fit_cdf = lambda x : make_interp_spline(x, al.pdf2cdf(x, y), 5)(x)

   ### Perform fit tests if specified, and compile results into result_row for saving or display.
   if fit_tests:
      if not save:
         print(f"Fit test results for {ana['fit_type']}:")
      else:
         logger.info(f"Fit test results for {ana['fit_type']}:")
      for test_name in fit_tests:
         test = al.fit_test_lib[test_name]
         stat, pvalue = test['func'](data, fit_cdf,len(params)/2)
         result_row[f"{test_name} Statistic"] = stat
         result_row[f"{test_name} P-Value"] = pvalue
         if not save:
            print(f"  {test_name}: statistic={stat:.6g}, p-value={pvalue:.6g}")
         else:
            logger.info(f"  {test_name}: statistic={stat:.6g}, p-value={pvalue:.6g}")

   ### Generate plots with fit and compile threshold results into result_row for saving or display.
   summary_lines = [f"Fit type: {ana['fit_type']}"]
   summary_lines.extend([f"{key}: {value:.6g}" for key, value in param_dict.items()])
   summary_lines.extend([f"{test_name} Statistic: {result_row[f"{test_name} Statistic"]:.6g}"for test_name in fit_tests])
   summary_text = "\n".join(summary_lines)
   threshold = plot_hist_with_fit(data, x, y, ana['data_type'], result_row['Channel'], summary_text=summary_text)
   if threshold is not None:
      result_row[f"{ana['threshold']*100:.2f}% Threshold"] = threshold
      if not save:
         print(f"{ana['threshold']*100:.2f}% threshold: {threshold:.6g}\n")
      else:
         logger.info(f"{ana['threshold']*100:.2f}% threshold: {threshold:.6g}")

   ### Add to results list for saving to file later
   return result_row