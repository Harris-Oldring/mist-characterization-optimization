import os
import openpyxl # Necessary for writing to .xlsx
import argparse
import csv
import textwrap
import logging
from characterization_utils import (
    load_file,
    landau_fit,
    landau_star_gauss_fastest,
    gauss_fit,
    times2event_rates,
    exp_mod_gauss_fit,
    landau_star_gauss_fit_fastest,
    langauss_fit,
    pdf2cdf,
    remove_overflow2,
    average_event_rate,
    num_of_events,
    duration,
    average_generic,
    kolmogorov_smirnov,
    anderson_darling,
    chi_squared,
    chi_squared_per_ndof,
    get_thresh
)
from scipy.interpolate import interp1d, make_interp_spline
from scipy.stats import exponnorm, landau, norm
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
import pandas as pd
from landaupy import langauss

n_baseline = 80 # This is the number of samples used to establish a baseline for each event (called N Samples Baseline on CoMPASS - sort of)
# I don't know why this has been set to 80. 256 is what is normally used on the CoMPASS GUI to get the energy measurements
FSR = 1000 # Full Scale Range in mV
bits = 10 # Number of bits in the digitizer
lsb = FSR/(2**bits-1) # Least Significant Bit in mV (-1 because the range starts at 0 and not ideal transition width) 
# Use this to convert ADC to a voltage in mV: voltage = ADC_counts * lsb - digitizer_offset
digitizer_offset = 148+8 # https://npg.dl.ac.uk/MIDAS/MIDASWebServices/VME/docs/UM3356_V1751_UserManual_rev16.pdf p. 23
# Digitizer offset is the amount by which the digitizer shifts the baseline of the waveform,  to ensure that large voltages can be represented without overflow. 
# I don't know why 148+8 was chosen
polarity = 'positive' # Polarity of the signal, either 'positive' or 'negative'. This is needed to determine how to apply the digitizer offset correction when converting ADC counts to voltage.


class Characterize:
   def __init__(self, n_channels, parent_dir, scope='both', general_analysis_names=['Number of Events', 'Sample Duration', 'Average Event Rate', 'Average Baseline'], fit_analysis_names=['Langauss Height', 'Exponentially Modified Gaussian Energy'], fit_tests=['chi_squared_per_ndof'], save=None, mode='w', plots=None, log=None, clean_up=True):
      '''
      n_channels (int): Number of channels to analyze.
      parent_dir (str): Parent directory containing the RAW subdirectory with channel data files.
      scope (str): Scope of analysis, either 'individual', 'aggregate', or 'both' (default: 'both').
         Note: 'individual' analyzes each channel separately, 'aggregate' combines all channels for analysis, and 'both' performs analysis on all channels individually and together.
      general_analysis_names (list of str): List of general analyses to perform (default: ['Number of Events', 'Sample Duration', 'Average Event Rate', 'Average Baseline']).
      fit_analysis_names (list of str): List of fit analyses to perform (default: ['Landau-Gaussian Height', 'Exponentially Modified Gaussian Energy']).
      fit_tests (list of str): List of fit tests to perform, options include 'kolmogorov_smirnov', 'anderson_darling', 'chi_squared', 'chi_squared_per_ndof' (default: ['chi_squared_per_ndof']).
      plots (str or None): File path to save plots as a PDF, or None to not save plots (default: None).
      save (str or None): File path to save results as a CSV, or None to not save results (default: None).
         Note: If None, results will be printed to console instead of saved to file.
      log (str or None): File path for logging output (default: 'characterization.log').
      clean_up (bool): Whether to clean up intermediate files after saving results (default: True).
      '''
      
      # Configure logging
      if log is None:
         log = 'characterization.log'
      logging.basicConfig(
         filename=log,
         level=logging.WARNING,
         format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
         datefmt='%Y-%m-%d %H:%M:%S',
         force=True
      )
      self.logger = logging.getLogger(__name__)
      self.logger.info("Characterization started")
      
      # Redirect warnings to logging
      logging.captureWarnings(True)
      
      
      '''
      HOW TO CONFIGURE GENERAL ANALYSES:
      ----------------------------------
      Each general analysis is defined by a dictionary containing the following keys:
      name: A descriptive name for the general analysis, used for labeling results and plots (e.g., 'Average Event Rate').
      description: A brief description of what the analysis does.
      func: The function used to perform the general analysis.
      args: Supplemental arguments to be supplied to the analysis function if necessary
      input_data: A list of data types required for the analysis (e.g., 'Time', 'Baseline').
      units: The units of the output metric
      plot: A boolean indicating whether this analysis creates a figure for plotting.
      ----------------------------------
      '''
      self.general_analyses_config = [
         {
            'name': 'Average Event Rate',
            'description': 'Compute the average event rate from timestamp data.',
            'func': average_event_rate,
            'args': None,
            'input_data': ['Time'],
            'units': 'events/s',
            'plot': False
         },
         {
            'name': 'Number of Events',
            'description': 'Compute the Total number of events.',
            'func': num_of_events,
            'args': None,
            'input_data': ['Energy', 'Overflows'],
            'units': 'events',
            'plot': False
         },
         {
            'name': 'Sample Duration',
            'description': 'Compute the duration of the sample.',
            'func': duration,
            'args': None,
            'input_data': ['Time'],
            'units': 's',
            'plot': False
         },
         {
            'name': 'Average Baseline',
            'description': 'Measure average baseline and its variability from baseline/time data.',
            'func': average_generic,
            'args': ['Baseline', 'mV'],
            'input_data': ['Time', 'Baseline'],
            'units': 'mV',
            'plot': True
         },
         {
            'name': 'Average Height',
            'description': 'Measure average height and its variability from height/time data.',
            'func': average_generic,
            'args': ['Height', 'mV'],
            'input_data': ['Time', 'Height'],
            'units': 'mV',
            'plot': True
         },
         {
            'name': 'Average Energy',
            'description': 'Measure average energy and its variability from energy/time data.',
            'func': average_generic,
            'args': ['ADC [channel]', ''],
            'input_data': ['Time', 'Energy'],
            'units': 'ADC [Channel]',
            'plot': True
         }
      ]

      '''
      HOW TO CONFIGURE FIT ANALYSES:
      ------------------------------
      Each fit analysis is defined by a dictionary containing the following keys:
      name: A descriptive name for the fit analysis, used for labeling results and plots (e.g., 'Landau-Gauss Height').
      data_type: The type of data being analyzed (e.g., 'Height', 'Energy', 'Time').
      data_transform_function: A function to transform the raw data before fit analysis, or None if no transformation is needed (e.g., times2event_rates for converting time data to event rates).
      fit_func: The function used to fit the data (e.g., landau_fit, exp_mod_gauss_fit, gauss_fit).
      pdf_func: A lambda function that takes x and the fit parameters and returns the corresponding PDF values, used for plotting and fit tests.
      param_names: A list of parameter names corresponding to the fit parameters returned by fit_func, used for compiling results into a structured format.
      fit_type: A string describing the type of fit performed (e.g., 'Landau', 'Exp Mod Gauss', 'Gauss'), used for labeling results and plots.
      xlabel: The label for the x-axis in plots, describing the quantity being analyzed (e.g., 'Wavelength Peak', 'ADC Channel', 'Event Rate').
      units: The units for the quantity being analyzed, used for labeling plots and results (e.g., 'mV', 'Events/s'), or an empty string if no units are applicable.
      threshold: A float representing the threshold to be calculated and plotted based on the fitted CDF, or None if no threshold is to be calculated (e.g., 0.001 for a 0.1% threshold).
      ------------------------------
      '''
      self.fit_analyses_config = [
         {
            'name': 'Landau Height',
            'title': 'Distribution of Waveform Peaks',
            'data_type': 'Height',         
            'data_transform_function': None,
            'fit_func': landau_fit,
            'pdf_func': lambda x, params: landau.pdf(x, loc=params[0], scale=params[2]),
            'param_names': ['mu', 'sigma_mu', 'c', 'sigma_c'],
            'fit_type': 'Landau',
            'xlabel': 'Wavelength Peak',
            'units': 'mV',
            'threshold' : 0.001
         },
         {
            'name': 'Old (wrong) Langauss Height',
            'title': 'Distribution of Waveform Peaks',
            'data_type': 'Height',
            'data_transform_function': None,
            'fit_func': landau_star_gauss_fit_fastest,
            'pdf_func': lambda x, params: landau_star_gauss_fastest(params[0], params[2], params[4], params[6], np.min(x), np.max(x))(x),
            'param_names': ['mu', 'sigma_mu', 'c', 'sigma_c', 'mean', 'sigma_mean', 'std', 'sigma_std'],
            'fit_type': 'Old Langauss',
            'xlabel': 'Wavelength Peak',
            'units': 'mV',
            'threshold' : 0.001
         },
         {
            'name': 'Langauss Height',
            'title': 'Distribution of Waveform Peaks',
            'data_type': 'Height',
            'data_transform_function': None,
            'fit_func': langauss_fit,
            'pdf_func': lambda x, params: langauss.pdf(x, landau_x_mpv=params[0], landau_xi=params[2], gauss_sigma=params[4]),
            'param_names': ['landau_x_mpv', 'sigma_landau_x_mpv', 'landau_xi', 'sigma_landau_xi', 'gauss_sigma', 'sigma_gauss_sigma'],
            'fit_type': 'Langauss',
            'xlabel': 'Wavelength Peak',
            'units': 'mV',
            'threshold' : 0.001
         },
         {
            'name': 'Exponentially Modified Gaussian Energy',
            'title': 'Energy Spectrum',
            'data_type': 'Energy',
            'data_transform_function': None,
            'fit_func': exp_mod_gauss_fit,
            'pdf_func': lambda x, params: exponnorm.pdf(x, params[0], loc=params[2], scale=params[4]),
            'param_names': ['K', 'sigma_K', 'mean', 'sigma_mean', 'std', 'sigma_std'],
            'fit_type': 'Exponentially Modified Gaussian',
            'xlabel': 'ADC [Channel]',
            'units': '',
            'threshold' : None
         },
         {
            'name': 'Gaussian Event Rate', # NOTE: This doesn't seem to be an appropriate way of analyzing event rate, but I have left it here anyways
            'data_type': 'Time',
            'data_transform_function': times2event_rates,
            'fit_func': gauss_fit,
            'pdf_func': lambda x, params: norm.pdf(x, loc=params[0], scale=params[2]),
            'param_names': ['mean', 'sigma_mean', 'std', 'sigma_std'],
            'fit_type': 'Gaussian',
            'xlabel': 'Event Rate',
            'units': 'Events/s',
            'threshold' : None
         }
      ]

      '''
      HOW TO CONFIGURE FIT TESTS:
      ---------------------------
      Each fit test is defined by a key corresponding to the test name (e.g., 'kolmogorov_smirnov') and a value that is a dictionary containing:
      func: The function that performs the fit test, which should take the data and the fitted CDF as inputs and return the test statistic and p-value (e.g., kolmogorov_smirnov).
      name: A descriptive name for the fit test, used for labeling results (e.g., 'Kolmogorov-Smirnov').
      ---------------------------
      '''
      self.fit_tests_config = {
         'kolmogorov_smirnov': {
            'func': kolmogorov_smirnov,
            'name': 'Kolmogorov-Smirnov' 
         },
         'anderson_darling': {
            'func': anderson_darling,
            'name': 'Anderson-Darling'
         },
         'chi_squared': {
            'func': chi_squared,
            'name': 'Chi-Squared'
         },
         'chi_squared_per_ndof': {
            'func': chi_squared_per_ndof,
            'name': 'Chi-Squared per NDOF'
         }
      }

      # From user input
      ## Attribute assignment
      self.n_channels = n_channels
      self.parent_dir = parent_dir
      self.scope = scope
      self.general_analyses = general_analysis_names 
      self.fit_analyses = fit_analysis_names
      self.fit_tests = fit_tests
      self.save = save 
      self.mode = mode
      self.plots = plots
      self.clean_up = clean_up

      ## Validation and Error Handling
      if not os.path.isdir(parent_dir): # Ensure parent directory exists
         self.logger.error(f"Parent directory does not exist: {parent_dir}")
         raise ValueError(f"Parent directory does not exist: {parent_dir}")
      if self.scope not in ['individual', 'aggregate', 'both']: # Ensure valid scope input
         self.logger.error(f"Invalid scope: {self.scope}. Must be 'individual', 'aggregate', or 'both'.")
         raise ValueError(f"Invalid scope: {self.scope}. Must be 'individual', 'aggregate', or 'both'.")
      available_analysis_names = [a['name'] for a in self.general_analyses_config]
      for analysis_name in self.general_analyses: # Ensure that each specified analysis is configured
         if analysis_name not in available_analysis_names:
            self.logger.error(f"general_analyses '{analysis_name}' is not configured. Available general_analyses: {available_analysis_names}")
            raise ValueError(f"general_analyses '{analysis_name}' is not configured. Available general_analyses: {available_analysis_names}")
      available_analysis_names = [a['name'] for a in self.fit_analyses_config]
      for analysis_name in self.fit_analyses: # Ensure that each specified analysis is configured
         if analysis_name not in available_analysis_names:
            self.logger.error(f"fit_analyses '{analysis_name}' is not configured. Available fit_analyses: {available_analysis_names}")
            raise ValueError(f"fit_analyses '{analysis_name}' is not configured. Available fit_analyses: {available_analysis_names}")
      if self.save is not None: # Add .csv extension to self.save if not already present
         self.save = self.save + ".csv" if not self.save.endswith(".csv") else self.save
      if self.plots is not None: # Add .pdf extension to self.plots if not already present
         self.plots = self.plots + ".pdf" if not self.plots.endswith(".pdf") else self.plots

      # Folder and data setup
      self.raw_dir = os.path.join(self.parent_dir, "RAW")
      if not os.path.isdir(self.raw_dir): # Ensure RAW directory exists within parent directory
         self.logger.error(f"RAW subdirectory not found: {self.raw_dir}")
         raise FileNotFoundError(f"RAW subdirectory not found: {self.raw_dir}")
      self.data_type_opts = ["Height", "Baseline", "Energy", "Channel", "Time"]
      self.data_type_overflow_opts = [False, False, True, False, False] # This indicates which data types have overflow events that need to be removed for fitting and general analyses.

      # Data saving setup
      self.fit_results_list = []
      self.general_fit_results_list = []
      self.pdf_pages = PdfPages(self.plots) if self.plots else None

      # Initialize self.aggregate_data, self.channel_indices, and self.individual_channel_data
      self.retrieve_data()
   
   def retrieve_data(self):
      '''
      Retrieves and aggregates data from all channels based on the specified data types.
      Loads data for each channel, aggregates it into a single structure for analysis, and also keeps track of channel boundaries for individual analyses.
      Loads:
         self.aggregate_data (dict): A dictionary where keys are data types and values are lists of aggregated data across all channels.
         self.channel_indices (list): A list of indices indicating the boundaries of each channel's data within the aggregated structure, useful for individual channel analyses.
         self.individual_channel_data (dict): A dictionary where keys are data types and values are lists of data for each individual channel, structured for easy access during individual analyses.
      Returns:
         None (data is stored in instance variables for later use in analyses)
      '''

      ## Using self.n_channels and self.raw_dir, load data for all channels and aggregate into a single structure for analysis. 
      ## Also keep track of channel boundaries for individual analyses.
      self.aggregate_data = [[] for _ in range(len(self.data_type_opts))]
      self.channel_indices = [0]
      ### Extract data from each channel
      for i in range(self.n_channels):
         ### Get Channel i data file
         channel_token = f"CH{i}"
         candidates = [fname for fname in os.listdir(self.raw_dir)
                    if os.path.isfile(os.path.join(self.raw_dir, fname)) and channel_token in fname]
         channel_filename = candidates[0]
         file_path = os.path.join(self.raw_dir, channel_filename)
         ### Load data and append to aggregate structure, while keeping track of channel boundaries
         ret = load_file(file_path, FSR=FSR, bits=bits, digitizer_offset=digitizer_offset, n_baseline=n_baseline, polarity=polarity, lowmem=True)
         self.channel_indices.append(len(ret[0]) + self.channel_indices[i])
         for dtype_idx in range(len(self.aggregate_data)):
            for j in range(len(ret[dtype_idx])):
               self.aggregate_data[dtype_idx].append(ret[dtype_idx][j])

      self.aggregate_data,self.channel_indices = dict(zip(self.data_type_opts,np.array(self.aggregate_data))),np.array(self.channel_indices)

      ## Construct individual_channel_data dictionary where each key is a data_type 
      self.individual_channel_data = {}
      for i in range(len(self.data_type_opts)):
         channel_data = []
         for j in range(len(self.channel_indices)-2):
            channel_data.append(self.aggregate_data[self.data_type_opts[i]][self.channel_indices[j]:self.channel_indices[j+1]])
         channel_data.append(self.aggregate_data[self.data_type_opts[i]][self.channel_indices[-2]:])
         self.individual_channel_data[self.data_type_opts[i]] = channel_data
   
   def make_fit_cdf(self, clean_data, fit_analysis, params):
      xmin, xmax = np.min(clean_data), np.max(clean_data) # Consider making this defined based on all of the data for this data type across all channels if we want to use the same CDF for all channels
      if xmin == xmax:
         self.logger.warning(f"Data has zero range (xmin == xmax == {xmin}). Returning zero CDF.")
         return lambda x: np.zeros_like(x) if np.ndim(x) else 0.0

      x_grid = np.linspace(xmin, xmax, 2000)
      y_pdf = fit_analysis['pdf_func'](x_grid, params)
      y_pdf = np.maximum(y_pdf, 0)
      cdf = lambda x : make_interp_spline(x_grid, pdf2cdf(x_grid, y_pdf), 5)(x)
      # plt.title('Fitted CDF') # Debugging line to visualize the fitted PDF 
      # plt.plot(x_grid, y_pdf, label='Fitted PDF') # Debugging line to visualize the fitted PDF
      # plt.show()
      # plt.title('Fitted CDF') # Debugging line to visualize the fitted CDF
      # plt.plot(x_grid, cdf(x_grid), label='Fitted CDF') # Debugging line to visualize the fitted CDF
      # plt.show()
      return cdf

   def plot_general_page(self, metrics, title, scope, channel, source=None, figure=None):
      if not self.pdf_pages:
         return

      if figure is not None:
         fig = figure
      else:
         fig, ax = plt.subplots(figsize=(10, 6))
         ax.axis('off')
         heading = f"General Analysis - {source if source else 'General'}"
         subtitle = f"Scope: {scope}, Channel: {channel if channel is not None else 'all'}"
         summary_lines = [heading, subtitle, '']
         summary_lines += [f"{key}: {value}" for key, value in metrics.items()]
         fig.text(0.01, 0.99, "\n".join(summary_lines), fontsize=10, va='top', family='monospace')
         fig.tight_layout()

      self.pdf_pages.savefig(fig)
      plt.close(fig)
   
   def plot_hist_with_fit(self, data, xfit, yfit, fit_analysis, channel, summary_text=None):
      '''
      Plots a histogram with a fitted probability density function.
      '''
      # Load in plotting parameters from analysis and construct figure
      xlabel, fit_type, units, threshold = fit_analysis['xlabel'], fit_analysis['fit_type'], fit_analysis['units'], fit_analysis['threshold']
      xlabel += f" ({units})" if units else ""
      scope = f"Channel {channel}" if channel != 'all' else "Aggregate"
      fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(10, 9))
   
      ## PDF Fit plot
      ax1.set_title(f"{fit_analysis['title']} ({scope})")
      ax1.set_xlabel(xlabel)
      ax1.set_ylabel("Frequency")
      ax1.hist(data, bins=round(np.sqrt(len(data))), density=True,histtype="step")
      ax1.plot(xfit, yfit, label=f'{fit_type} PDF Fit')
      ax1.legend()

      ## CDF Fit plot
      y_cdf = pdf2cdf(xfit, yfit)
      ax2.set_title(f"{fit_analysis['title']} ({scope})")
      ax2.set_xlabel(xlabel)
      ax2.set_ylabel("Frequency")
      ax2.set_ylim(1e-4,1.1)
      ax2.hist(data, bins=round(np.sqrt(len(data))), density=True, cumulative=True, histtype="step")
      ax2.plot(xfit, y_cdf, label=f'{fit_type} CDF Fit')
      ### Plot threshold, if Applicable
      if threshold is not None:
         thresh = get_thresh(xfit, y_cdf,rate=threshold)
         cdf_at_thresh = make_interp_spline(xfit, y_cdf, 5)(thresh)
         ax2.plot(thresh, cdf_at_thresh, label=f"{threshold*100:.2f}% Threshold", marker="x", linestyle="")
         ax2.annotate(f"Threshold = {thresh:.3f} {units}", xy=(thresh, cdf_at_thresh), xytext=(thresh+15, cdf_at_thresh*0.4), textcoords='data')
      ax2.set_yscale('log')
      ax2.legend()

      ## Add summary text detailing important parameters, etc.
      if summary_text:
         fig.tight_layout(rect=[0, 0.12, 1, 0.95])
         fig.text(0.01, 0.02, summary_text, fontsize=8, va='bottom', ha='left')
      else:
         fig.tight_layout()

      ## Save or show plot
      if self.pdf_pages and self.save:
         self.logger.info(f"Saving plot for {fit_analysis['name']} ({scope}) to PDF")
         self.pdf_pages.savefig(fig)
         plt.close(fig)
      elif self.pdf_pages:
            self.logger.info(f"Displaying plot for {fit_analysis['name']} ({scope})")
            plt.show()

      if threshold is not None:
         return thresh
      return None

   def add_results_table_to_pdf(self, table_data=None):
      """
      Add a formatted table page to an existing PdfPages object.

      Parameters
      ----------
      pdf_pages : PdfPages
        Existing PdfPages object.

      table_data : list[list]
        Table contents where:
        - first row is the header row
        - all rows have equal length
      """

      if table_data is None:
         table_data = self.general_fit_results_list

      if not table_data or len(table_data) < 2:
        return

      # Transpose if more than 3 rows total
      # if len(table_data) > 3:
      #   table_data = list(map(list, zip(*table_data)))

      # Separate headers from body
      WRAP_WIDTH = 24

      headers = [
         textwrap.fill(str(x), WRAP_WIDTH, break_long_words=False, break_on_hyphens=False)
         for x in table_data[0]
      ]

      body = []

      for row in table_data[1:]:
         wrapped_row = []
         for i, cell in enumerate(row):
            width = 28 if i == 0 else 14
            wrapped_row.append(textwrap.fill(str(cell), width, break_long_words=False, break_on_hyphens=False))
         body.append(wrapped_row)

      # Figure sizing
      n_rows = len(body) + 1
      n_cols = len(headers)

      fig_width = max(8, n_cols * 1.6)
      fig_height = max(3, n_rows * 0.8 + 1.5)

      fig, ax = plt.subplots(figsize=(fig_width, fig_height))
      ax.axis('off')

      # Title
      fig.suptitle(
         "General Analyses Results",
         fontsize=14,
         fontweight='bold',
         y=0.96
      )

      # Build table
      table = ax.table(
         cellText=body,
         colLabels=headers,
         loc='center',
         cellLoc='center'
      )

      # Enable wrapping inside cells
      for cell in table.get_celld().values():
         cell.get_text().set_wrap(True)
      
      cells = table.get_celld()

      # Find maximum number of wrapped lines in each row
      row_line_counts = {}

      for (row, col), cell in cells.items():

         text = cell.get_text().get_text()
         n_lines = text.count('\n') + 1

         if row not in row_line_counts:
            row_line_counts[row] = n_lines
         else:
            row_line_counts[row] = max(row_line_counts[row], n_lines)

      # Apply uniform height to every cell in each row
      for row, max_lines in row_line_counts.items():
         # Base height
         height = 0.12 * max_lines
         for col in range(n_cols):
            if (row, col) in cells:
               cells[(row, col)].set_height(height)

      # Styling
      table.auto_set_font_size(False)
      table.set_fontsize(10)
      table.scale(1.1, 1.5)

      # APA-like formatting
      for (row, col), cell in table.get_celld().items():
         cell.set_text_props(va='center')
         ## Header row
         if row == 0:
            cell.set_text_props(weight='bold')
            cell.set_facecolor('#EAEAEA')
            cell.set_linewidth(1.2)
         else:
            cell.set_linewidth(0.8)

        ## Left-align first column (labels)
         if col == 0:
            cell.set_text_props(ha='left')
 
         ## Subtle borders
         cell.set_edgecolor('black')

      # Save page
      plt.tight_layout(rect=[0.03, 0.03, 0.97, 0.90])

      self.pdf_pages.savefig(fig)
      plt.close(fig)

   def reformat_to_excel(self):
      ## Load the CSV
      df = pd.read_csv(self.save)
      df['Channel'] = df['Channel'].astype(str)

      output_excel = self.save.rsplit('.', 1)[0] + ".xlsx"
      ##  Use ExcelWriter to save multiple sheets
      with pd.ExcelWriter(output_excel, engine='openpyxl') as writer:
         for data_type in df['Analysis'].unique():
            ### Filter the data for the current type
            subset = df[df['Analysis'] == data_type].copy()
            
            ### Apply sorting
            subset['sort_key'] = subset['Channel'].apply(lambda ch: -1 if ch.lower() == 'all' else int(ch)) # All goes to top row
            subset = subset.sort_values('sort_key').drop(columns=['sort_key', 'Analysis'])
            
            ### Remove empty columns
            subset = subset.dropna(axis=1, how='all')

            ### Pivot to Channels
            other_cols = [c for c in subset.columns if c not in ['Channel', 'Data Type', 'sort_key']]
            column_order = ['Channel'] + other_cols
            subset = subset[column_order]

            ### Write subset to its own sheet
            subset.to_excel(writer, sheet_name=data_type, index=False)
            
      message = f"Successfully created {output_excel} with sheets: {list(df['Analysis'].unique())}"
      print(message)
      self.logger.info(message)

   def perform_fit_analysis(self, data, fit_analysis, scope, channel=None):
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
         output_line = f"Analysis: {fit_analysis['name']}, Scope: {scope}, Channel: {channel if channel is not None else 'all'}"

         ### Clean data and fit distribution to it based on the specified analysis configuration.  
         params = fit_analysis['fit_func'](data)
         param_dict = dict(zip(fit_analysis['param_names'], params))

         ### Compile results into a structured format for saving or display, including fit parameters and overflow information.
         result_row = {
            'Analysis': fit_analysis['name'],
            'Data Type': fit_analysis['data_type'],
               'Scope': scope,
               'Channel': channel if channel is not None else 'all',
               'Fit Type': fit_analysis['fit_type'],
            }
         result_row.update(param_dict)
        
         ### Display output if not saving to file
         if not self.save:
            print(output_line)
            print(f"{fit_analysis['fit_type']} fit: {param_dict}")
         else:
            self.logger.info(output_line)

         ### Generate fit CDF and plots
         fit_cdf = self.make_fit_cdf(data, fit_analysis, params)
         x = np.linspace(np.min(data), np.max(data), 1000)
         y = fit_analysis['pdf_func'](x, params)

         ### Perform fit tests if specified, and compile results into result_row for saving or display.
         if self.fit_tests:
            if not self.save:
               print(f"Fit test results for {fit_analysis['fit_type']}:")
            else:
               self.logger.info(f"Fit test results for {fit_analysis['fit_type']}:")
            for test_key in self.fit_tests:
               test = self.fit_tests_config[test_key]
               stat, pvalue = test['func'](data, fit_cdf,len(params)/2)
               result_row[f"{test['name']} Statistic"] = stat
               result_row[f"{test['name']} P-Value"] = pvalue
               if not self.save:
                  print(f"  {test['name']}: statistic={stat:.6g}, p-value={pvalue:.6g}")
               else:
                  self.logger.info(f"  {test['name']}: statistic={stat:.6g}, p-value={pvalue:.6g}")
            if not self.save:
               print()

         ### Generate plots with fit and compile threshold results into result_row for saving or display.
         summary_lines = [f"Fit type: {fit_analysis['fit_type']}"]
         summary_lines.extend([f"{key}: {value:.6g}" for key, value in param_dict.items()])
         summary_text = "\n".join(summary_lines)
         threshold = self.plot_hist_with_fit(data, x, y, fit_analysis, result_row['Channel'], summary_text=summary_text)
         if threshold is not None:
            result_row[f"{fit_analysis['threshold']*100:.2f}% Threshold"] = threshold
            if not self.save:
               print(f"{fit_analysis['threshold']*100:.2f}% threshold: {threshold:.6g}\n")
            else:
               self.logger.info(f"{fit_analysis['threshold']*100:.2f}% threshold: {threshold:.6g}")

         ### Add to results list for saving to file later
         self.fit_results_list.append(result_row)

   def run(self):
      '''
      TODO: Write this description
      '''

      # Necessary to append to General sheet
      if self.mode=='a':
         copy_df = pd.read_excel(self.save.rsplit('.', 1)[0] + ".xlsx", sheet_name='General')

      general_analysis_header = ['Statistic']

      scopes = ['individual', 'aggregate'] if self.scope == 'both' else [self.scope]
      overflows = ["Overflow Events"]
      for scope in scopes:
         
         # Clean the data for the specified scope and extract overflow metrics
         if scope == 'individual':
            self.individual_channel_data['Overflows'] = []
            ## Iterate over each channel
            for channel_idx in range(self.n_channels):
               ### Get overflows and mask for the channel
               mask, channel_overflows = remove_overflow2(self.individual_channel_data['Energy'][channel_idx])
               general_analysis_header.append(f"Channel {channel_idx}")
               overflows.append(channel_overflows)
               self.individual_channel_data['Overflows'].append(channel_overflows)
               ### Apply mask to all data types for the channel which need overflows removed
               for data_type in np.array(self.data_type_opts)[self.data_type_overflow_opts]:
                  self.individual_channel_data[data_type][channel_idx] = np.array(self.individual_channel_data[data_type][channel_idx])[mask].tolist()
               
         elif scope == 'aggregate':
            ### Get overflows and mask for the aggregate data
               mask, channel_overflows = remove_overflow2(self.aggregate_data['Energy'])
               general_analysis_header.append(f"All Channels")
               overflows.append(channel_overflows)
               self.aggregate_data['Overflows'] = channel_overflows
               ### Apply mask to all data types for the aggregate data which need overflows removed
               for data_type in np.array(self.data_type_opts)[self.data_type_overflow_opts]:
                  self.aggregate_data[data_type] = np.array(self.aggregate_data[data_type])[mask].tolist()
         
         # Perform all fit analyses for each specified data type and compile results into self.fit_results_list for saving or display.
         for fit_analysis_name in self.fit_analyses:
               # Find the analysis config matching this name
               fit_analysis = next(a for a in self.fit_analyses_config if a['name'] == fit_analysis_name)
               data_type = fit_analysis['data_type']
            
               if scope == 'individual':
                  for channel_idx in range(self.n_channels):
                     data = self.individual_channel_data[data_type][channel_idx]
                     # Apply data transform if specified
                     if fit_analysis['data_transform_function']:
                        # print(f"Transforming {data_type} data for {scope} scope with {fit_analysis['data_transform_function'].__name__}") # DEBUG
                        data = fit_analysis['data_transform_function'](data)
                     self.perform_fit_analysis(data, fit_analysis, scope, channel_idx)
               elif scope == 'aggregate':
                  data = self.aggregate_data[data_type]
                  # Apply data transform if specified
                  if fit_analysis['data_transform_function']:
                     # print(f"Transforming {data_type} data for {scope} scope with {fit_analysis['data_transform_function'].__name__}") # DEBUG
                     data = fit_analysis['data_transform_function'](data)
                  self.perform_fit_analysis(data, fit_analysis, scope)

      # Perform all general analyses and compile results into self.general_fit_results_list for saving or display.
      ## Add header and overflows
      self.general_fit_results_list.append(general_analysis_header)
      self.general_fit_results_list.append(overflows)
      ## Perform the analyses and compile results
      for general_analysis_name in self.general_analyses:
         ### Find the analysis config matching this name
         analysis = next(a for a in self.general_analyses_config if a['name'] == general_analysis_name)
         result_row = [f"{analysis['name']} ({analysis['units']})"]
         ### Perform the analysis for the specified scope
         for scope in scopes:
            if scope == 'individual':
               for channel_idx in range(self.n_channels):
                  data_inputs = [self.individual_channel_data[input_type][channel_idx] for input_type in analysis['input_data']]
                  if not analysis['plot']:
                     result = analysis['func'](*data_inputs, *analysis['args']) if analysis['args'] is not None else analysis['func'](*data_inputs)
                  else:
                     result,fig,ax = analysis['func'](*data_inputs, *analysis['args']) if analysis['args'] is not None else analysis['func'](*data_inputs)
                     ax.set_title(ax.get_title() + f" (Channel {channel_idx})")
                     if self.pdf_pages:
                        self.pdf_pages.savefig(fig)
                     plt.close(fig)
                  result_row.append(result)
            elif scope == 'aggregate':
               data_inputs = [self.aggregate_data[input_type] for input_type in analysis['input_data']]
               if not analysis['plot']:
                  result = analysis['func'](*data_inputs, *analysis['args']) if analysis['args'] is not None else analysis['func'](*data_inputs)
               else:
                  result,fig,ax = analysis['func'](*data_inputs, *analysis['args']) if analysis['args'] is not None else analysis['func'](*data_inputs)
                  ax.set_title(ax.get_title() + " (All Channels)")
                  if self.pdf_pages:
                     self.pdf_pages.savefig(fig)
                  plt.close(fig)
               result_row.append(result)
         ### Add results to list for saving to file later
         self.general_fit_results_list.append(result_row)

      # Save the results
      ## Add the general analysis results to the PDF
      ## Close PDF if it was used and print location of saved plots.
      if self.pdf_pages:
         self.add_results_table_to_pdf()
         self.pdf_pages.close()
         if self.save:
            message = f"General analysis results table and fit plots saved to: {self.plots}"
            print(f"\n{message}")
            self.logger.info(message)
      
      ## Save results to Excel if specified,
      if self.save:
         ### Save fit results to CSV, convert to Excel, and remove original CSV
         if self.fit_results_list:
            all_keys = set()
            for row in self.fit_results_list:
               all_keys.update(row.keys())
            fieldnames = sorted(all_keys)
            # print(f"Saving fit analysis results to {self.save} with fields: {fieldnames}") # Debugging line to verify fieldnames before saving
            with open(self.save, self.mode, newline='') as csvfile:
               writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
               if self.mode == 'w': # I'm pretty sure this prevents writing the header multiple times if appending
                  writer.writeheader()
               writer.writerows(self.fit_results_list)
            message = f"Fit analysis results saved to: {self.save}"
            print(message)
            self.logger.info(message)

            self.reformat_to_excel()
            print(message)
            self.logger.info(message)
            excel_mode = 'a'
         else:
            message = "No fit analysis results to save."
            print(message)
            self.logger.warning(message)
            excel_mode = 'w'
      
         ## Save general results to Excel sheet in the same file as fit results
         if self.general_fit_results_list:
            # if len(self.general_fit_results_list) > 3: # Transpose if more than 3 rows total to make more readable in Excel
            #    self.general_fit_results_list = np.transpose(np.array([np.array(row) for row in self.general_fit_results_list]))
            general_results_df = pd.DataFrame(
               self.general_fit_results_list[1:],
               columns=self.general_fit_results_list[0]
            )

            # print(general_results_df) # Debugging line to visualize general results before saving to Excel
            output_excel = self.save.rsplit('.', 1)[0] + ".xlsx"

            if self.mode=='a':
               general_results_df = pd.concat([copy_df,general_results_df],axis=0)
            print(general_results_df)

            with pd.ExcelWriter(output_excel, engine='openpyxl', mode=excel_mode) as writer:
               general_results_df.to_excel(writer, sheet_name='General', index=False)

            message = f"General analysis results saved to 'General' sheet in {output_excel}"
            print(message)
            self.logger.info(message)
         else:
            message = "No general analysis results to save."
            print(message)
            self.logger.warning(message)

      # Clean up if specified
      if self.clean_up:
         os.remove(self.save)
         message = f"{self.save} has been removed after conversion to Excel."

def main():
   parser = argparse.ArgumentParser(description="Characterize data from multiple channels with various analyses and fit tests.")
   parser.add_argument('parent_dir', type=str, help="Parent directory containing RAW subdirectory with channel data files.")
   parser.add_argument('n_channels', type=int, help="Number of channels to analyze.")
   parser.add_argument('--scope', type=str, choices=['individual', 'aggregate', 'both'], default='both', help="Scope of analysis: 'individual', 'aggregate', or 'both' (default: 'both').")
   parser.add_argument('--general_analyses', nargs='+', default=['Number of Events', 'Sample Duration', 'Average Event Rate', 'Average Baseline'], help="List of general analyses to perform by name (default: ['Number of Events', 'Sample Duration', 'Average Event Rate', 'Average Baseline']).")
   parser.add_argument('--fit_analyses', nargs='+', default=['Langauss Height', 'Exponentially Modified Gaussian Energy'], help="List of fit analyses to perform by name (default: ['Langauss Height', 'Exponentially Modified Gaussian Energy']).")
   parser.add_argument('--fit_tests', nargs='+', choices=['kolmogorov_smirnov', 'anderson_darling', 'chi_squared', 'chi_squared_per_ndof'], default=['chi_squared_per_ndof'], help="List of fit tests to perform (default: ['chi_squared_per_ndof']).")
   parser.add_argument('--save', type=str, default=None, help="File path to save results as a CSV, or None to not save results (default: None).")
   parser.add_argument('--mode', type=str, choices=['w', 'a'], default='w', help="File mode for saving results: 'w' for write (overwrite) or 'a' for append (default: 'w').")
   parser.add_argument('--plots', type=str, default=None, help="File path to save plots as a PDF. If plots and save is specified, plots are saved to the specified PDF file. If plots is specified but save is None, plots are displayed, but not saved to a file. Currently no support for appending to pdf. (default: None).")
   parser.add_argument('--log', type=str, default='characterization.log', help="File path for logging output (default: 'characterization.log').")
   parser.add_argument('--no_clean_up', action='store_true', help="Whether to not clean up intermediate files after saving results.")
   args = parser.parse_args()

   characterizer = Characterize(
      n_channels=args.n_channels,
      parent_dir=args.parent_dir,
      scope=args.scope,
      general_analysis_names=args.general_analyses,  # Pass analysis names as analysis_names parameter
      fit_analysis_names=args.fit_analyses,  # Pass analysis names as analysis_names parameter
      fit_tests=args.fit_tests,
      save=args.save,
      mode=args.mode,
      plots=args.plots,
      log=args.log,
      clean_up= (not args.no_clean_up)
   )
   characterizer.run()

if __name__ == "__main__":
   main()
