import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm, exponnorm, landau, kstest, anderson, anderson_ksamp, chisquare, gaussian_kde
from scipy.interpolate import BarycentricInterpolator,interp1d,make_interp_spline
from scipy.integrate import quad
from scipy.optimize import curve_fit,root_scalar
import uproot

# DATA PROCESSING FUNCTIONS
## Loading and basic processing

def load_file(file, FSR=1000, bits=10, digitizer_offset=148+8, n_baseline=80, n_max=None, polarity='positive', lowmem=False):
   '''
   file - the filename of the .root file you wish to load
   FSR (Optional) - The full scale range of the digitizer in mV. Default 1000mV
   bits (Optional) - The number of bits in the digitizer. Default 10
   digitizer_offset (Optional) - The amount by which the digitizer shifts the baseline of the waveform, to ensure that large voltages can be represented without overflow. Default 148+8
   n_baseline (Optional) - The number of samples at the beginning of the waveform to use for baseline calculation. Default 80
   polarity (Optional) - The polarity of the signals, either 'positive' or 'negative'. Default 'positive'
   n_max (Optional) - The maximum number of events you want to consider. Default None
   lowmem (Optional) - If True returns the waveforms from the "Samples" branch. Default False
   '''

   lsb = FSR/(2**bits-1) # Least Significant Bit in mV (-1 because the range starts at 0 and not ideal transition width) 
   # Use this to convert ADC to a voltage in mV: voltage = ADC_counts * lsb - digitizer_offset

   # Use uproot to load the root file and extract the relevant data.
   rootfile = uproot.open(file)
   if len(rootfile.keys(filter_classname="TTree"))==0:
      print(rootfile.keys())
      print(rootfile.keys(filter_classname="TTree"))
      print(rootfile.classnames())
      raise FileExistsError("root file contains 0 TTrees")
   tree = rootfile[rootfile.keys(filter_classname="TTree")[0]] # Uses the first TTree in the root file

   # Initialize lists to store the extracted data
   height = []
   baseline = []

   # Extract the relevant branches from the TTree
   n = tree.num_entries
   n_entries = min(n_max, n) if n_max else n
   waves = tree["Samples"].array(entry_stop=n_entries, library="np")
   energy = tree["Energy"].array(entry_stop=n_entries, library="np")
   channel = tree["Channel"].array(entry_stop=n_entries, library="np")
   timestamp = tree["Timestamp"].array(entry_stop=n_entries, library="np")
   time = timestamp/1e12 # Convert picoseconds to seconds

   # Process each waveform to extract the height and baseline information
   for wave in waves:
      b = np.mean(wave[:n_baseline])
      if polarity == 'positive':
         m = np.max(wave[n_baseline:])
      elif polarity == 'negative':
         m = np.min(wave[n_baseline:])
      h = (m-b)*lsb
      height.append(h)
      baseline.append(b*lsb)

   # Convert energy to mV and apply digitizer offset correction 
   # (This actually doesn't make sense to do here. I will just leave this as ADC [Channel]. (This is actually in units of charge, and is proportional to energy))
   # energy = energy*lsb - digitizer_offset 

   # If lowmem is False, we also store the waveforms with the digitizer offset removed
   if not lowmem: waves.append(wave-digitizer_offset)
   sorted_indices = np.argsort(time) # Sorts based on time
   #print('%s loaded. %.1f seconds of data.' % (file, (max(time)-min(time))/1e9))
   return np.array(height)[sorted_indices], \
   np.array(baseline)[sorted_indices], \
   np.array(energy)[sorted_indices], \
   np.array(channel)[sorted_indices], \
   np.array(time)[sorted_indices], \
   None if lowmem else np.array(waves)[sorted_indices]

## Cleaning/converting
def remove_overflow(target_data, energy_data):
   '''
   target_data - The data you want to remove overflow events from (e.g., height)
   energy_data - The energy data corresponding to the target data, used to identify overflow events

   Identifies overflow events based on the energy data and removes them from the target data, since overflow data turns up as
   energies where the energy is at its maximum representable value (a power of 2 - 1).
   Returns the cleaned target data and the number of overflow events removed.
   '''
   if len(target_data) != len(energy_data):
      raise ValueError("target_data and energy_data must have the same length for overflow removal")

   max_val = max(energy_data)
   if np.log2(max_val+1).is_integer(): # Highly suspicious, likely overflow
      mask = energy_data!=max_val
      return target_data[mask], len(target_data)-len(target_data[mask])
   else: # No overflow
      return target_data, 0

def remove_overflow2(energy_data):
   '''
   energy_data - The energy data corresponding to the target data, used to identify overflow events

   Identifies overflow events based on the energy data and removes them from the target data, since overflow data turns up as
   energies where the energy is at its maximum representable value (2^N - 1).
   Returns a mask that can be applied to the data to remove overflow events and the number of overflow events identified.
   '''
   
   max_val = max(energy_data)
   if np.log2(max_val+1).is_integer(): # Highly suspicious, likely overflow
      mask = energy_data!=max_val
      return mask, len(mask)-np.sum(mask)
   else: # No overflow
      return np.ones_like(energy_data, dtype=bool), 0

def remove_overflow3(energy_data, FSR=1000, bits=10, digitizer_offset=148+8):
   '''
   energy_data - The energy data corresponding to the target data, used to identify overflow events

   Identifies overflow events based on the energy data and removes them from the target data, since overflow data turns up as
   energies where the energy is at its maximum representable value (2^N - 1).
   Returns a mask that can be applied to the data to remove overflow events and the number of overflow events identified.
   '''
   lsb = FSR/(2**bits-1) # Least Significant Bit in mV (-1 because the range starts at 0 and not ideal transition width)
   max_val = (max(energy_data) + digitizer_offset)/lsb # Convert back to ADC counts to check for overflow
   # print(f"\nMax energy value: {max(energy_data):.2f} mV, which corresponds to ADC count: {max_val:.2f}\n")
   if np.log2(max_val+1).is_integer(): # Highly suspicious, likely overflow
      mask = energy_data!=max(energy_data)
      return mask, len(mask)-np.sum(mask)
   else: # No overflow
      return np.ones_like(energy_data, dtype=bool), 0

def times2event_rates(times, sigma_s=None, resolution=1000):
   """
   times: array of timestamps in s
   sigma_s: absolute smoothing factor in s (e.g., 5.0 for 5s window)
   """
   times = np.sort(np.asarray(times))
   n_events = len(times)
    
   if n_events < 2:
      return np.array([]), np.array([])

   duration = times[-1] - times[0]
   rate_axis = np.linspace(times[0], times[-1], resolution)
    
   # Calculate KDE
   kde = gaussian_kde(times)
    
   # If the user provides a specific sigma in s, we must convert it
   # to the 'relative' bandwidth scipy expects: bw = sigma / data_std
   if sigma_s:
      data_std = np.std(times)
      kde.set_bandwidth(bw_method=sigma_s / data_std)
    
   # Evaluate and scale from 'density' to 'events per s'
   # kde.evaluate(x) * total_n = Rate
   rate = kde.evaluate(rate_axis) * n_events
    
   return rate

## PDF/CDF conversions and convolutions
def pdf2cdf(x,y_pdf):
   '''
   Given a set of x,y_pdf values which make up a pdf, 
   returns the y_cdf values which correspond to the cdf of that distribution with the same x values
   '''
   dx = np.diff(x)
   y_cdf = np.empty_like(y_pdf)
   y_cdf[0] = 0
   y_cdf[1:] = np.cumsum((y_pdf[:-1] + y_pdf[1:]) / 2 * dx)
   return y_cdf / y_cdf[-1]

def cdf_hist(n, bins):
   '''
   returns half_bins, cdf, the x and y data that makes up your discrete cdf
   '''
   cdf = np.cumsum(n).astype(np.float64)
   cdf /= cdf[-1]  # Normalize so last value is 1.0
   half_bins = np.array([(bins[i] + bins[i+1]) / 2 for i in range(len(bins) - 1)])
   return half_bins, cdf

def landau_star_gauss(mu, c, x0, sigma, l, u, grid_size=300, cdf=False):
   '''
   Returns an interpolation of a Landau distribution convoluted with a Gaussian distribution
   mu,c are parameters corresponding to the location and spread of the Landau Distribution
   x0,sigma are parameters corresponding to mean and standard distribution of the Gaussian Distribution
   u,l are the upper and lower bounds for the x-values of your distribution
   '''
   # Define a fine grid over the data range
   #  x_grid = np.linspace(l, u, grid_size) # For speed w/ interp1d
   x_grid = (np.polynomial.chebyshev.chebpts1(grid_size)+1)*(u-l)/2+u # For use w/ BarycentricInterpolator
   conv_values = []
   for xi in x_grid:
       # Narrow limits to data range for stability
       result = quad(lambda t: landau.pdf((xi - t), loc=mu, scale=c) * norm.pdf(t, x0, sigma),
                     l, u, limit=100)[0]
       conv_values.append(result)
   conv_values = np.array(conv_values)
   # Normalize 
   norm_factor = np.trapezoid(conv_values, x_grid) # For speed
   conv_values /= norm_factor
   # Interpolate
   # return interp_func = interp1d(x_grid, conv_values, kind='linear', bounds_error=False, fill_value=0) # For speed
   if cdf:
      return BarycentricInterpolator(x_grid,pdf2cdf(x_grid,conv_values)) # Better Interpolation   
   return BarycentricInterpolator(x_grid,conv_values) # Better Interpolation

def faster_landau_star_gauss(mu, c, x0, sigma, l, u, grid_size=300, cdf=False):
   '''
   Returns an interpolation of a Landau distribution convoluted with a Gaussian distribution
   mu,c are parameters corresponding to the location and spread of the Landau Distribution
   x0,sigma are parameters corresponding to mean and standard distribution of the Gaussian Distribution
   u,l are the upper and lower bounds for the x-values of your distribution
   '''
   # Define a fine grid over the data range
   x_grid = np.linspace(l, u, grid_size) # For speed w/ interp1d
   #  x_grid = (np.polynomial.chebyshev.chebpts1(grid_size)+1)*(u-l)/2+u # For use w/ BarycentricInterpolator
   conv_values = []
   for xi in x_grid:
       # Narrow limits to data range for stability
       result = quad(lambda t: landau.pdf((xi - t), loc=mu, scale=c) * norm.pdf(t, x0, sigma),
                     l, u, limit=100)[0]
       conv_values.append(result)
   conv_values = np.array(conv_values)
   # Normalize 
   norm_factor = np.trapezoid(conv_values, x_grid) # For speed
   conv_values /= norm_factor
   # Interpolate
   if cdf:
      return interp1d(x_grid, pdf2cdf(x_grid, conv_values), kind='linear', bounds_error=False, fill_value=0) # For speed
   return interp1d(x_grid, conv_values, kind='linear', bounds_error=False, fill_value=0) # For speed
   # return BarycentricInterpolator(x_grid,conv_values) # Better Interpolation

def landau_star_gauss_fastest(mu, c, x0, sigma, l, u, grid_size=300, cdf = False):
   '''
   Returns an interpolation of a Landau distribution convoluted with a Gaussian distribution
   mu,c are parameters corresponding to the location and spread of the Landau Distribution
   x0,sigma are parameters corresponding to mean and standard distribution of the Gaussian Distribution
   u,l are the upper and lower bounds for the x-values of your distribution
   '''
   assert isinstance(grid_size,int)
   x_grid = np.linspace(l, u, int(grid_size))
   dx = x_grid[1] - x_grid[0]
   landau_vals = landau.pdf(x_grid, loc=mu, scale=c)
   gauss_vals  = norm.pdf(x_grid, loc=x0, scale=sigma)
   conv = np.convolve(landau_vals, gauss_vals, mode='same') * dx
   conv /= np.trapezoid(conv, x_grid)
   if cdf:
      return interp1d(x_grid, pdf2cdf(x_grid,conv))
   return interp1d(x_grid, conv)

# GENERAL ANALYSIS FUNCTIONS
def average_event_rate(time_data, overflows):
   '''
   Calculate the average event rate for the provided timestamps.
   Returns a dictionary of metrics for the general analysis flow.
   '''
   times = np.asarray(time_data)
   if times.size < 2:
      return np.nan
   duration = np.max(times) - np.min(times)
   if duration <= 0:
      return np.nan
   n = float(len(times))+overflows
   return f"{n/duration:.2f} ± {float(np.sqrt(n))/duration:.2f}"

def average_baseline(time_data, baseline_data, spike_threshold=5.0):
   '''
   Compute a simple baseline stability metric and count baseline spikes.
   Returns metrics, figure, and axis.
   '''
   if time_data is None or baseline_data is None:
      return {'Baseline Stability': np.nan, 'Baseline Spike Count': np.nan}, None

   time_data = np.asarray(time_data)
   baseline_data = np.asarray(baseline_data)
   if time_data.size < 2 or baseline_data.size < 2 or time_data.size != baseline_data.size:
      return {'Baseline Stability': np.nan, 'Baseline Spike Count': np.nan}, None

   sort_idx = np.argsort(time_data)
   t = time_data[sort_idx]
   b = baseline_data[sort_idx]

   # dt = np.diff(t)
   # db = np.diff(b)
   # valid = dt > 0
   # if not np.any(valid):
   #    stability = np.nan
   # else:
   #    slopes = db[valid] / dt[valid]
   #    stability = float(np.nanstd(slopes))

   # spikes = int(np.sum(np.abs(db) > spike_threshold))
   fig, ax = plt.subplots(figsize=(10, 4))
   # ax.plot(t, b, marker='.', linestyle='-', markersize=2)
   ax.scatter(t, b, s=5)
   ax.set_title('Baseline vs Time')
   ax.set_xlabel('Time (s)')
   ax.set_ylabel('Baseline (mV)')
   ax.grid(True, linestyle='--', alpha=0.5)
   # annotation = f"Baseline Stability = {stability:.3g}\nSpike Count = {spikes}"
   # ax.text(0.99, 0.02, annotation, transform=ax.transAxes, ha='right', va='bottom', fontsize=9,
   #         bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))
   fig.tight_layout()
   return f'{np.mean(b):.2f} ± {np.std(b):.2f}', fig, ax

def average_generic(time_data, target_data, data_type, units):
   '''
   Compute a simple baseline stability metric and count baseline spikes.
   Returns metrics, figure, and axis.
   '''
   if time_data is None or target_data is None:
      return {'Baseline Stability': np.nan, 'Baseline Spike Count': np.nan}, None

   time_data = np.asarray(time_data)
   target_data = np.asarray(target_data)
   if time_data.size < 2 or target_data.size < 2 or time_data.size != target_data.size:
      return {'Baseline Stability': np.nan, 'Baseline Spike Count': np.nan}, None

   sort_idx = np.argsort(time_data)
   t = time_data[sort_idx]
   sorted = target_data[sort_idx]

   fig, ax = plt.subplots(figsize=(10, 4))
   ax.scatter(t, sorted, s=5)
   ax.set_title(f'{data_type} vs Time')
   ax.set_xlabel('Time (s)')
   ylabel = f'{data_type} ({units})' if units else data_type
   ax.set_ylabel(ylabel)
   ax.grid(True, linestyle='--', alpha=0.5)
   fig.tight_layout()
   return f'{np.mean(sorted):.2f} ± {np.std(sorted):.2f}', fig, ax

def num_of_events(energy_data, overflows):
   return len(energy_data)+overflows

def duration(time_data):
   times = np.sort(np.asarray(time_data))
   return times[-1]-times[0]

# FITTING FUNCTIONS
def gauss_fit(data):
   '''
   Given a set of data, fits a Gauss distribution
   Returns:
   mean,sigma_mean,std,sigma_std - The fit parameters mu,c as well as an estimate of their error
   '''
   print("Fitting Gaussian...")
   n,bins = np.histogram(data,bins=int(np.sqrt(len(data))),density=True)
   half_bins = np.array([(bins[i]+bins[i+1])/2 for i in range(len(bins)-1)])
   print(np.mean(data),np.std(data))
   popt, pcov = curve_fit(lambda x, mu, c: norm.pdf(x, loc=mu, scale=c), half_bins, n,p0=[np.mean(data), np.std(data)])
   mean,std = popt
   sigma_mean,sigma_std=np.sqrt(np.diag(pcov))
   return mean,sigma_mean,std,sigma_std

def landau_fit(data):
   '''
   Given a set of data, fits a Landau distribution
   Returns:
   mu,sigma_mu,c,sigma_c - The fit parameters mu,c as well as an estimate of their error
   '''
   n,bins = np.histogram(data, bins=int(np.sqrt(len(data))))
   half_bins, cdf = cdf_hist(n,bins)
   popt, pcov = curve_fit(lambda x, mu, c: landau.cdf(x, loc=mu, scale=c), half_bins, cdf)
   mu,c = popt
   sigma_mu,sigma_c=np.sqrt(np.diag(pcov))
   return mu,sigma_mu,c,sigma_c

def landau_star_gauss_fit(data,mu_l=1,mu_u=500,c_l=1,c_u=200,x0_l=1,x0_u=500,std_l=0.01,std_u=150):
   '''
   Given a set of data, fits a Landau distribution convoluted with a Gaussian distribution
   Returns:
   mu,sigma_mu,c,sigma_c,mean,sigma_mean,std,sigma_std - The fit parameters mu,c,mean,std as well as an estimate of their error
   '''
   l,u = min(data),max(data)
   n,bins = np.histogram(data, bins=int(np.sqrt(len(data))))
   half_bins, cdf = cdf_hist(n,bins)
   mu0,_,c0,_ = landau_fit(data)
   x00, std0 = np.mean(half_bins), np.std(half_bins)/2

   # Fit with bounds to prevent negative sigma
   bounds = ([mu_l, c_l, min(np.min(half_bins),x0_l), std_l], [mu_u, c_u, max(np.max(half_bins),x0_u), std_u])
   if mu0>mu_u or mu0<mu_l: mu0=(mu_l+mu_u)/2
   if c0>c_u or c0<c_l: c0=(c_l+c_u)/2
   if x00>x0_u or x00<x0_l: x00=(x0_l+x0_u)/2
   if std0>mu_u or std0<std_l: std0=(std_l+std_u)/2

   # Initial guesses: based on prior Landau fit and data estimates
   p0 = [mu0, c0, x00, std0]  # mu, c, mean, std
   popt, pcov = curve_fit(lambda x, mu, c,x0, sigma: landau_star_gauss(mu, c, x0, sigma,l,u,cdf=True)(x),
                       half_bins, cdf, p0=p0, bounds=bounds)
   mu,c,mean,std = popt
   sigma_mu,sigma_c,sigma_mean,sigma_std = np.sqrt(np.diag(pcov))
   return mu,sigma_mu,c,sigma_c,mean,sigma_mean,std,sigma_std

def landau_star_gauss_fit_fastest(data,mu_l=1,mu_u=500,c_l=1,c_u=200,x0_l=1,x0_u=500,std_l=0.01,std_u=150):
   '''
   Given a set of data, fits a Landau distribution convoluted with a Gaussian distribution
   Returns:
   mu,sigma_mu,c,sigma_c,mean,sigma_mean,std,sigma_std - The fit parameters mu,c,mean,std as well as an estimate of their error
   '''
   l,u = min(data),max(data)   
   n,bins = np.histogram(data, bins=int(np.sqrt(len(data))))
   half_bins, cdf = cdf_hist(n,bins)
   mu0,_,c0,_ = landau_fit(data)
   x00, std0 = np.mean(half_bins), np.std(half_bins)/2

   # Fit with bounds to prevent negative sigma
   bounds = ([mu_l, c_l, min(np.min(half_bins),x0_l), std_l], [mu_u, c_u, max(np.max(half_bins),x0_u), std_u])
   if mu0>mu_u or mu0<mu_l: mu0=(mu_l+mu_u)/2
   if c0>c_u or c0<c_l: c0=(c_l+c_u)/2
   if x00>x0_u or x00<x0_l: x00=(x0_l+x0_u)/2
   if std0>mu_u or std0<std_l: std0=(std_l+std_u)/2

   # Initial guesses: based on prior Landau fit and data estimates
   p0 = [mu0, c0, x00, std0]  # mu, c, mean, std
   popt, pcov = curve_fit(lambda x, mu, c,x0, sigma: landau_star_gauss_fastest(mu, c, x0, sigma,l,u,cdf=True)(x),
                       half_bins, cdf, p0=p0, bounds=bounds)
   mu,c,mean,std = popt
   sigma_mu,sigma_c,sigma_mean,sigma_std = np.sqrt(np.diag(pcov))
   return mu,sigma_mu,c,sigma_c,mean,sigma_mean,std,sigma_std

def exp_mod_gauss_fit(data):
   '''
   Given a set of data, fits an exponentially modified Gaussian distribution
   Returns:
   K,sigma_K,mean,sigma_mean,std,sigma_std - The fit parameters mu,c as well as an estimate of their error
   '''
   n,bins = np.histogram(data,bins=int(np.sqrt(len(data))),density=True)
   half_bins = np.array([(bins[i]+bins[i+1])/2 for i in range(len(bins)-1)])
   p0 = np.array([1,np.mean(data),np.std(data)])
   popt, pcov = curve_fit(lambda x, K, mean, std: exponnorm.pdf(x, K, mean,std), half_bins, n,p0=p0)
   K,mean,std = popt
   sigma_K,sigma_mean,sigma_std=np.sqrt(np.diag(pcov))
   return K,sigma_K,mean,sigma_mean,std,sigma_std

# ANALYSIS FUNCTIONS
## Fit-testing
def kolmogorov_smirnov(data, fit_cdf,n_params=None):
   '''
   Performs a Kolmogorov-Smirnov test to compare the empirical distribution of the data with the fitted distribution.
   Returns the KS statistic and p-value.
   '''
   ret = kstest(data, lambda x: fit_cdf(x))
   return ret.statistic, ret.pvalue

# anderson_darling does not seem to be working properly, likely due to the fact that anderson is 
# designed for testing against specific distributions rather than arbitrary fitted CDFs and 
# anderson_ksamp is designed for testing whether two samples come from the same distribution rather
#  than testing a sample against a fitted CDF. 
def anderson_darling(data, fit_cdf,n_params=None):
   '''
   Performs an Anderson-Darling test to compare the empirical distribution of the data with the fitted distribution.
   Returns the AD statistic and critical values.
   '''
   ret = anderson_ksamp([data, fit_cdf(np.sort(data))])
   # ret = anderson(data, dist=lambda x: fit_cdf(x)) # Does not work because dist must be one of the predefined distributions in scipy
   return ret.statistic, ret.pvalue

def chi_squared(data, fit_cdf, n_params):
   '''
   Performs a Chi-Squared test to compare the empirical distribution of the data with the fitted distribution.
   Returns the Chi-Squared statistic and p-value.
   '''
   n, bins = np.histogram(data, bins=round(np.sqrt(len(data))), density=False)
   # print(f"Number of bins: {len(bins)-1}")
   expected_probs = fit_cdf(bins[1:]) - fit_cdf(bins[:-1])

   # Remove really small expected values to avoid issues with the chi-squared test
   mask = expected_probs > 1e-6
   n = n[mask]
   expected_probs = expected_probs[mask]

   # Normalize`
   expected_probs /= np.sum(expected_probs)
   expected = np.sum(n) * expected_probs

   ret = chisquare(n,f_exp=expected,ddof=n_params)
   return ret.statistic, ret.pvalue

def chi_squared_per_ndof(data, fit_cdf, n_params):
   '''
   Performs a Chi-Squared test to compare the empirical distribution of the data with the fitted distribution.
   Returns the Chi-Squared statistic and p-value.
   '''
   n, bins = np.histogram(data, bins=round(np.sqrt(len(data))), density=False)
   ndof = len(n) - 1
   expected_probs = fit_cdf(bins[1:]) - fit_cdf(bins[:-1])

   # Remove really small expected values to avoid issues with the chi-squared test
   mask = expected_probs > 1e-6
   n = n[mask]
   expected_probs = expected_probs[mask]

   # Normalize`
   expected_probs /= np.sum(expected_probs)
   expected = np.sum(n) * expected_probs

   ret = chisquare(n,f_exp=expected,ddof=n_params)
   return ret.statistic/ndof, ret.pvalue

## Other
def get_thresh(x,y_cdf,rate=1e-3):
   interp = make_interp_spline(x,y_cdf,5)
   return root_scalar(lambda t:interp(t)-rate,bracket=(min(x),max(x))).root
