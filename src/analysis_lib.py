import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm, exponnorm, landau, kstest, anderson, anderson_ksamp, chisquare, gaussian_kde, skew, poisson
from scipy.interpolate import BarycentricInterpolator,interp1d,make_interp_spline
from scipy.integrate import quad
from scipy.optimize import curve_fit,root_scalar
from landaupy import langauss

# FUNCTIONS
## UTILITY
def cdf_hist(n, bins):
   '''
   returns half_bins, cdf, the x and y data that makes up your discrete cdf
   '''
   cdf = np.cumsum(n).astype(np.float64)
   cdf /= cdf[-1]  # Normalize so last value is 1.0
   half_bins = np.array([(bins[i] + bins[i+1]) / 2 for i in range(len(bins) - 1)])
   return half_bins, cdf

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


## FIT FUNCTIONS
def gauss_fit(data):
   '''
   Given a set of data, fits a Gauss distribution
   Returns:
   popt - The fit parameters mu,sigma
   sigma_popts - The error in mu and sigma obtained through curve_fit
   '''
   n,bins = np.histogram(data,bins=int(np.sqrt(len(data))),density=True)
   half_bins, cdf = cdf_hist(n,bins)

   popt, pcov = curve_fit(lambda x, mu, c: norm.pdf(x, loc=mu, scale=c), half_bins, n,p0=[np.mean(data), np.std(data)])
   sigma_popts=np.sqrt(np.diag(pcov))
   return popt,sigma_popts

def landau_fit(data):
   '''
   Given a set of data, fits a Landau distribution
   Returns:
   popt - The fit parameters mu and c
   sigma_popts - The error in mu and c obtained through curve_fit
   '''
   n,bins = np.histogram(data, bins=int(np.sqrt(len(data))))
   half_bins, cdf = cdf_hist(n,bins)

   popt, pcov = curve_fit(lambda x, mu, c: landau.cdf(x, loc=mu, scale=c), half_bins, cdf)
   sigma_popts=np.sqrt(np.diag(pcov))
   return popt,sigma_popts

def langauss_fit(data):
   '''
   Given a set of data, fits a Langauss distribution
   Returns:
   popt - The fit parameters x_mpv, xi, and Gaussian sigma
   sigma_popts - The error in x_mpv, xi, and Gaussian sigma obtained through curve_fit
   '''
   n,bins = np.histogram(data, bins=int(np.sqrt(len(data))))
   half_bins, cdf = cdf_hist(n,bins)

   landau_params,landau_param_errs = landau_fit(data)
   mu0,c0 = landau_params
   p0 = [mu0, c0, 6*c0]  # landau mpv, landau width, 6x landau width
   popt, pcov = curve_fit(
      lambda x, landau_x_mpv, landau_xi, gauss_sigma: langauss.cdf(x, landau_x_mpv=landau_x_mpv, landau_xi=landau_xi, gauss_sigma=gauss_sigma), 
      half_bins, 
      cdf, 
      p0=p0,
      bounds=([-np.inf, 1e-6, -np.inf], [np.inf, np.inf, np.inf]) # Constrain xi and sigma to be > 0
   )
   landau_x_mpv, landau_xi, gauss_sigma = popt

   retries = 0
   while gauss_sigma < 0: # This is a good indicator for a poor fit
      retries += 1
      p0 = [landau_x_mpv, landau_xi/2, 25] # The most likely explanation of a bad fit is big initial guess for landau_xi
      popt, pcov = curve_fit(
         lambda x, landau_x_mpv, landau_xi, gauss_sigma: langauss.cdf(x, landau_x_mpv=landau_x_mpv, landau_xi=landau_xi, gauss_sigma=gauss_sigma), 
         half_bins, 
         cdf, 
         p0=p0,
         bounds=([-np.inf, 1e-6, -np.inf], [np.inf, np.inf, np.inf]) # Constrain xi to be > 0
      )
      landau_x_mpv, landau_xi, gauss_sigma = popt
      if retries > 5:
         raise RuntimeError(f"Distribution cannot be fit. {retries+1} attempts made.")

   sigma_popts=np.sqrt(np.diag(pcov))
   return popt, sigma_popts

def exp_mod_gauss_fit(data):
   '''
   Given a set of data, fits an exponentially modified Gaussian distribution
   Returns:
   popt - The fit parameters K, mu, and sigma
   sigma_popts - The error in K, mu, and sigma obtained through curve_fit
   '''
   n,bins = np.histogram(data,bins=int(np.sqrt(len(data))),density=True)
   half_bins = np.array([(bins[i]+bins[i+1])/2 for i in range(len(bins)-1)])

   m, s, g = np.mean(data), np.std(data), skew(data)
   while g<=0.5:
      g*=2
   tau = s * np.cbrt(g/2)  
   variance_diff = s**2 - tau**2
   if variance_diff > 0 and tau > 0:
      p0 = np.array([tau / np.sqrt(variance_diff), m - tau, np.sqrt(variance_diff)]) # See https://en.wikipedia.org/wiki/Exponentially_modified_Gaussian_distribution
   else:
      # Fallback to a generic, safe initial guess if moments produce invalid math
      p0 = np.array([1.0, m, s]) 

   popt, pcov = curve_fit(lambda x, K, mean, std: exponnorm.pdf(x, K, mean,std), half_bins, n,p0=p0)
   sigma_popts=np.sqrt(np.diag(pcov))
   return popt,sigma_popts

def poisson_fit(data):
   '''
   Given a set of data, fits a Poisson distribution
   Returns:
   popt - The fit parameters K, mu, and sigma
   sigma_popts - The error in K, mu, and sigma obtained through curve_fit
   '''
   popt, pcov = curve_fit(lambda k,lam : poisson.pmf(k,lam), np.arange(0, max(data)+1), np.bincount(data))
   sigma_popts=np.sqrt(np.diag(pcov))
   return popt,sigma_popts


##FIT TESTING
def kolmogorov_smirnov(data, fit_cdf, n_params):
   '''
   Performs a Kolmogorov-Smirnov test to compare the empirical distribution of the data with the fitted distribution.
   Returns the KS statistic and p-value.
   '''
   ret = kstest(data, lambda x: fit_cdf(x))
   return ret.statistic, ret.pvalue

def chi_squared(data, fit_cdf, n_params, per_ndof=False):
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

   ndof = len(n) - 1
   chi2=ret.statistic/ndof if per_ndof else ret.statistic

   return chi2, ret.pvalue



# ANALYSIS CONFIG

'''
HOW TO CONFIGURE FIT ANALYSES:
------------------------------
Each fit analysis is given as a dictionary containing the following keys:
data_type: The type of data being analyzed (e.g., 'Height', 'Energy', 'Time').
fit_func: The function used to fit the data (e.g., landau_fit, exp_mod_gauss_fit, gauss_fit).
pdf_func: A lambda function that takes x and the fit parameters and returns the corresponding PDF values, used for plotting and fit tests.
params: A list of the parameters of the fit function in the order they are stored
threshold: A float representing the threshold to be calculated and plotted based on the fitted CDF, or None if no threshold is to be calculated (e.g., 0.001 for a 0.1% threshold).
------------------------------
'''
fit_lib = {
   'Landau': {
      'data_type': 'Height',   
      'fit_func': landau_fit,
      'pdf_func': lambda x, params: landau.pdf(x, *params),
      'params': ['mu', 'c'],
      'threshold' : 0.001,
   },
   'Langauss' : {
      'data_type': 'Height',
      'fit_func': langauss_fit,
      'pdf_func': lambda x, params: langauss.pdf(x, *params),
      'params': ['x_mpv', 'xi', 'gauss_sigma'],
      'threshold' : 0.001,
   },
   'EMG' : {
      'data_type': 'Energy',
      'fit_func': exp_mod_gauss_fit,
      'pdf_func': lambda x, params: exponnorm.pdf(x, *params),
      'params': ['K', 'mu', 'sigma'],
      'threshold' : None
   },
   'Poisson' : {
      'data_type': 'Energy',
      'fit_func': poisson_fit,
      'pdf_func': lambda k, params: poisson.pmf(k, *params),
      'params': ['lambda'],
      'threshold' : None
   },
}

fit_test_lib = {
   'KS': {
      'func': kolmogorov_smirnov,
      'args': None,
   },
   'chi2': {
      'func': chi_squared,
      'args': None,
   },
   'chi2/ndof': {
      'func': chi_squared,
      'args': [True,],
   },
}