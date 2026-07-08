import numpy as np
import analysis_lib as al
from scipy.interpolate import make_interp_spline
from scipy.optimize import root_scalar
import matplotlib.pyplot as plt

plot_config = {
    'Height': {
        'title': 'Distribution of Waveform Peaks',
        'xlabel': 'Wavelength Peak',
        'units': 'mV',
    },
    'Energy': {
        'title': 'Energy Spectrum',
        'xlabel': 'ADC [Channel]',
        'units': None,
    }
}

class FitResult:
   def __init__(self, data, ana_name, ch, fit_tests, logger=None, save=False):
      self.ana_name = ana_name
      self.ana = al.fit_lib[ana_name]
      self.ch = ch
      self.data = data
      self.params = []
      self.param_errs = []
      self.xgrid = []
      self.ypdf = []
      self.cdf = None
      self.test_results = {}
      self.thresh = None
      self.result_row = {}
      self.fig = None

      self.fit(fit_tests, logger=logger, save=save)

   def compute_params(self, display=False, logger=None):
      '''
      Compute the appropriate fit parameters given an array of data
      If display, then prints results to terminal
      If a logger is provided, these values will be logged at info level

      '''
      self.params, self.param_errs = self.ana['fit_func'](self.data)

      # Create output string
      out_str = ''
      for i in range(len(self.params)): out_str += f'{self.ana['params'][i]:^16}|'
      out_str += '\n'
      for i in range(len(self.params)): out_str += ('-'*15 + '-+')
      out_str += '\n'
      for i in range(len(self.params)): out_str += f'   {self.params[i]:>12.2f} |'
      out_str += '\n'
      for i in range(len(self.params)): out_str += f' ± {self.param_errs[i]:>12.2f} |'
      out_str += '\n'
      
      # Display or print to terminal as specified
      if display:
         print(out_str)
      if logger:
         logger.info(out_str)

   def fit(self, fit_tests, logger=None, save=False):
      display = not save
      # Display/log output header based on save status
      output_line = f"\nAnalysis: {self.ana['data_type']} data with {self.ana_name} fit, Channel: {self.ch}"
      if display:
         print(output_line)
         for _ in range(len(output_line)): print('=', end='')
         print()
      if logger:
         logger.info(output_line)

      # Fit distribution
      self.compute_params(display=display, logger=logger)

      # Generate fit CDF and plots
      self.generate_fit(display=display, logger=logger)

      # Perform fit tests if specified
      if fit_tests:
         for test_name in fit_tests:
            self.perform_fit_test(test_name, display=display, logger=logger)

      # Generate plots with fit results
      self.generate_fig(save)

      # Update result_row
      self.update_result_row()

   def generate_fig(self, save):
      '''
      Creates a figure containing a histogram with a fitted pdf, a histogram with a fitted cdf, and key fit information
      '''
      data = self.data
      nbins = round(np.sqrt(len(data)))
      plot_info = plot_config[self.ana['data_type']]
      title, xlabel, units = plot_info['title'], plot_info['xlabel'], plot_info['units']

      fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9))
      fig.suptitle(f'Channel {self.ch} {self.ana['data_type']} Data with {self.ana_name} Fit')

      x = self.xgrid

      ## PDF Fit plot
      ax1.set_title(title)
      if units: xlabel += f" ({units})"
      ax1.set_xlabel(xlabel)
      ax1.set_ylabel("Probability Density")
      ax1.hist(data, bins=nbins, density=True, histtype="step", label = 'Binned Data')
      ax1.plot(x, self.ypdf, label=f'{self.ana_name} Fit')
      ax1.legend()

      ## CDF Fit plot
      ax2.set_title(title)
      ax2.set_xlabel(xlabel)
      ax2.set_ylabel("Probability")
      ax2.set_ylim(1e-4,1.1)
      ax2.hist(data, bins=nbins, density=True, cumulative=True, histtype="step", label = 'Cumulative Binned Data')
      ax2.plot(x, self.cdf(x), label=f'{self.ana_name} Fit')

      ### Plot threshold, if Applicable
      if self.thresh:
         cdf_at_thresh = self.cdf(self.thresh)
         ax2.plot(self.thresh, cdf_at_thresh, label=f"{self.ana['threshold']*100:.2f}% Threshold", marker="x", linestyle="")
      ax2.set_yscale('log')
      ax2.legend()

      ## Add summary text detailing important parameters, etc.
      fig.tight_layout(rect=[0, 0.12, 1, 0.95])
      fig.text(0.01, 0.02, self.write_summary(), fontsize=8, va='bottom', ha='left')
      
      # Show figure if relevant
      if not save:
         plt.show()

      # Save figure
      self.fig = fig
      plt.close(fig)

   def generate_fit(self, grid_size=2000, display=False, logger=None):
      '''
      Generate grid_size values for self.xgrid and self.ypdf, and use these to create self.cdf
      If applicable, will update self.threshold based on cdf interpolation which will be printed/logged according to display and logger
      '''
      # Ensure the fit parameters have been computed
      if len(self.params) == 0:
         self.compute_params(self.data)

      # Generate xgrid, create corresponding pdf values, convert to cdf and interpolate
      self.xgrid = np.linspace(np.min(self.data), np.max(self.data), grid_size)
      self.ypdf = self.ana['pdf_func'](self.xgrid, self.params)
      self.cdf = make_interp_spline(self.xgrid, al.pdf2cdf(self.xgrid, self.ypdf), 5)

      # Calculate threshold if applicable
      thresh_level = self.ana['threshold']
      if thresh_level:
         self.thresh = root_scalar(lambda t:self.cdf(t)-thresh_level,bracket=(min(self.xgrid),max(self.xgrid))).root
         out_str = f'{thresh_level*100:.2f}% threshold: {self.thresh:.6g}'
         if display:
            print(out_str)
         if logger:
            logger.info(out_str)

   def perform_fit_test(self, test_name, display=False, logger=None):
      '''
      Performs the fit test corresponding to test_name with the given data, and update self.test_results accordingly
      If display, then prints results to terminal
      If a logger is provided, these values will be logged at info level
      '''
      # Ensure a cdf interpolation has been generated
      if not self.cdf:
         self.generate_fit(self.data)

      # Perform the fit test
      test = al.fit_test_lib[test_name]
      if test['args']:  
         stat, pvalue = test['func'](self.data, self.cdf, len(self.params), *test['args'])
      else:
         stat, pvalue = test['func'](self.data, self.cdf, len(self.params))

      # Add to self.test_results
      self.test_results[f"{test_name} Statistic"] = stat
      self.test_results[f"{test_name} P-Value"] = pvalue

      # Display or print to terminal as specified
      out_str = f"{test_name} statistic={stat:.6g}, p-value={pvalue:.6g}"

      if display:
         print(out_str)
      if logger:
         logger.info(out_str)

   def update_result_row(self):
      '''
      Compile results into a structured format for saving to CSV or for display
      '''
      # Include channel and threshold
      self.result_row = {
         'Channel': self.ch if self.ch is not None else 'all',
      }
      if self.ana['threshold']: self.result_row[f'{self.ana['threshold']*100:.2f}% Threshold'] =  self.thresh
      
      # Include parameters and their errors
      param_dict = dict(zip(self.ana['params'], self.params))
      param_err_dict = dict(zip(f'{self.ana['params']} Error', self.param_errs))
      self.result_row.update(param_dict)
      self.result_row.update(param_err_dict)
      

      # Include fit-test result
      self.result_row.update(self.test_results)

   def write_summary(self):
      '''
      Writes a brief summary of results
      '''
      summary_lines = []
      # Parameter ± error
      summary_lines.extend([f'{self.ana['params'][i]}: {self.params[i]:.6g} ± {self.param_errs[i]:.2g}'  for i in range(len(self.params))])
      # Fit-test statistic
      statistic_keys = list(self.test_results.keys())[0::2]
      summary_lines.extend([f'{key}: {self.test_results[key]:.6g}' for key in statistic_keys])
      # Threshold
      if self.ana['threshold']: summary_lines.append(f'{self.ana['threshold']*100:.2f}% threshold: {self.thresh:.6g}')
    
      return "\n".join(summary_lines)