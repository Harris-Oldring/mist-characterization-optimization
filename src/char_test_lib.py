import pandas as pd
import numpy as np
from scipy import stats

'''
Change default to True to evaluate based on defined maximum and minimum rather than comparing to other scintillators 
'''
acceptance_lib = {
   'Event Rate': {
      'default': True,
      'std_results': True,
      'func': lambda std_results, ch: std_results[ch][3],
      'maximum': None,
      'minimum': None,
      'too_big': 'Unusually high event rate. Check for light leaks.',
      'too_small': 'Unusually low event rate.',
   },
   'Energy Overflows': {
      'default': True,
      'std_results': True,
      'func': lambda std_results, ch: std_results[ch][4],
      'maximum': None,
      'minimum': None,
      'too_big': 'Unusually high amount of energy saturation. (number of energy overflows)',
      'too_small': 'Unusually low amount of energy saturation. (number of energy overflows)',
   },
   'Langauss MPV': {
      'default': True,
      'std_results': False,
      'func': lambda fit_results, ch: fit_results['Langauss'][ch].params[0],  
      'maximum': None,
      'minimum': None,
      'too_big': 'Unusually high mpv of pulse height distribution. This indicates a larger-than-expected light yield.',
      'too_small': 'Unusually low mpv of pulse height distribution. This indicates a small light yield or noisy signal.',
   },
   'Langauss \u03C7\u00B2/ndof': { # chi^2/ndof
      'default': True,
      'std_results': False,
      'func': lambda fit_results, ch: fit_results['Langauss'][ch].test_results[f"chi2/ndof Statistic"],  
      'maximum': None,
      'minimum': None,
      'too_big': '\u03C7\u00B2/ndof of Langauss fit/height distribution is significantly higher than expected.',
      'too_small': '\u03C7\u00B2/ndof of Langauss fit/height distribution is significantly lower than expected.',
   },
   'Threshold': {
      'default': True,
      'std_results': False,
      'func': lambda fit_results, ch: fit_results['Langauss'][ch].thresh,  
      'maximum': None,
      'minimum': None,
      'too_big': 'Threshold is significantly higher than expected. Check light yield,',
      'too_small': 'Threshold is significantly lower than expected. Check light yield and noise levels.',
   },
   'Energy K': {
      'default': True,
      'std_results': False,
      'func': lambda fit_results, ch: fit_results['EMG'][ch].params[0],  
      'maximum': None,
      'minimum': None,
      'too_big': '$K$ parameter of energy spectrum is significantly higher than expected.',
      'too_small': '$K$ parameter of energy spectrum is significantly lower than expected.',
   },
   'Energy \u03BC': { # mu
      'default': True,
      'std_results': False,
      'func': lambda fit_results, ch: fit_results['EMG'][ch].params[1],  
      'maximum': None,
      'minimum': None,
      'too_big': '\u03BC parameter of energy spectrum is significantly higher than expected.',
      'too_small': '\u03BC parameter of energy spectrum is significantly lower than expected.',
   },
   'Energy \u03C3': { # sigma
      'default': True,
      'std_results': False,
      'func': lambda fit_results, ch: fit_results['EMG'][ch].params[2],  
      'maximum': None,
      'minimum': None,
      'too_big': '\u03C3 parameter of energy spectrum is significantly higher than expected.',
      'too_small': '\u03C3 parameter of energy spectrum is significantly lower than expected.',
   },
   'Energy \u03C7\u00B2/ndof': { # chi^2/ndof 
      'default': True,
      'std_results': False,
      'func': lambda fit_results, ch: fit_results['EMG'][ch].test_results[f"chi2/ndof Statistic"],  
      'maximum': None,
      'minimum': None,
      'too_big': '\u03C7\u00B2/ndof of EMG fit/energy spectrum is significantly higher than expected.',
      'too_small': '\u03C7\u00B2/ndof of EMG fit/energy spectrum is significantly lower than expected.',
   },
}

def calc_accept_param_range(outdir, cat_name, cat, scint_info):
   '''
   Calculates the acceptable parameter range
   '''
   minimum, maximum = cat['minimum'], cat['maximum'] # Use defined ranges user has requested
   if cat['default']:
      # Set the acceptable range to be [q1-iqr, q3+iqr] 
      col = [scint[cat_name] for scint in scint_info]
      q1,q3 = np.quantile(col,1/4), np.quantile(col,3/4)
      iqr = q3-q1
      minimum, maximum = q1-iqr*1.5, q3+iqr*1.5
   return minimum, maximum

def failure_message():
   '''
   Prints the appropriate failure message
   '''
   pass

def grubbs_test(data, potential_outlier, alpha = 0.05):
   '''
   https://www.itl.nist.gov/div898/handbook/eda/section3/eda35h1.htm
   https://www.geeksforgeeks.org/python/how-to-find-the-t-critical-value-in-python/
   '''
   G = np.abs(potential_outlier - np.mean(data)) / np.std(data)

   N = len(data) + 1
   significance_level = alpha / (2 * N)
   t_alpha = stats.t.ppf(1 - significance_level, N - 2)

   rhs = (N-1)/np.sqrt(N) * np.sqrt(t_alpha**2 / (N - 2 + t_alpha**2))
   return G > rhs

def pass_or_fail(outfolder, scint_lst, std_results, fit_results, logger=None):
   '''
   Determines whether or not a scintillator passes or fails and carries out the corresponding behaviour
   '''
   # Calculate acceptance parameter values for each scintilator 
   info = []
   for ch in range(len(scint_lst)):
      scint_info = {}
      for cat_name, cat in acceptance_lib.items():
         results = std_results if cat['std_results'] else fit_results
         scint_info[cat_name] =  cat['func'](results,ch)
      info.append(scint_info)

   # Calculate acceptable ranges for acceptance parameters
   maxima, minima = {},{}
   for cat_name, cat in acceptance_lib.items():
      minima[cat_name], maxima[cat_name] = calc_accept_param_range(outfolder, cat_name, cat, info)

   '''
   TODO: Finish writing this
   Needs to use Grubb's test to identify outliers if default behaviour and other scintillators have already passed
   Elif default, use iqr method 
   else use user inputted max/min

   Then needs to do all of the printing, results storage, plotting, etc.
   '''

def update_scintillator_results():
   '''
   Updates the `scintillator_results.csv`
   '''
   pass