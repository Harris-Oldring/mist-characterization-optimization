import numpy as np
from scipy.stats import norm, exponnorm, landau, kstest, anderson, anderson_ksamp, chisquare, gaussian_kde
from scipy.interpolate import BarycentricInterpolator,interp1d,make_interp_spline
from scipy.integrate import quad
from scipy.optimize import curve_fit,root_scalar
#from landaupy import langauss


#UTILITY
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

# FIT FUNCTIONS
def gauss_fit(data):
   '''
   Given a set of data, fits a Gauss distribution
   Returns:
   mean,sigma_mean,std,sigma_std - The fit parameters mu,c as well as an estimate of their error
   '''
   print("Fitting Gaussian...")
   n,bins = np.histogram(data,bins=int(np.sqrt(len(data))),density=True)
   half_bins, cdf = cdf_hist(n,bins)
   print(np.mean(data),np.std(data))
   popt, pcov = curve_fit(lambda x, mu, c: norm.pdf(x, loc=mu, scale=c), half_bins, n,p0=[np.mean(data), np.std(data)])
   sigma_popts=np.sqrt(np.diag(pcov))
   return popt,sigma_popts

def landau_fit(data):
   '''
   Given a set of data, fits a Landau distribution
   Returns:
   mu,sigma_mu,c,sigma_c - The fit parameters mu,c as well as an estimate of their error
   '''
   n,bins = np.histogram(data, bins=int(np.sqrt(len(data))))
   half_bins, cdf = cdf_hist(n,bins)
   popt, pcov = curve_fit(lambda x, mu, c: landau.cdf(x, loc=mu, scale=c), half_bins, cdf)
   sigma_popts=np.sqrt(np.diag(pcov))
   return popt,sigma_popts

# def langauss_fit(data):
#    '''
#    Given a set of data, fits a Langauss distribution
#    Returns:
#    landau_x_mpv, landau_xi, gauss_sigma - The fit parameters as well as an estimate of their error
#    '''
#    n,bins = np.histogram(data, bins=int(np.sqrt(len(data))))
#    half_bins, cdf = cdf_hist(n,bins)

#    mu0, c0 = landau_fit(data)[0]
#    p0 = [mu0, c0, 6*c0]  # mu, c, mean, std
#    popt, pcov = curve_fit(lambda x, landau_x_mpv, landau_xi, gauss_sigma: langauss.cdf(x, landau_x_mpv=landau_x_mpv, landau_xi=landau_xi, gauss_sigma=gauss_sigma), half_bins, cdf, p0=p0)
#    sigma_popts=np.sqrt(np.diag(pcov))
#    return popt,sigma_popts

def landau_star_gauss_fit(data,mu_l=1,mu_u=500,c_l=1,c_u=200,x0_l=1,x0_u=500,std_l=0.01,std_u=150, fast=False):
   '''
   Given a set of data, fits a Landau distribution convoluted with a Gaussian distribution
   Returns:
   mu,sigma_mu,c,sigma_c,mean,sigma_mean,std,sigma_std - The fit parameters mu,c,mean,std as well as an estimate of their error
   '''
   l,u = min(data),max(data)
   n,bins = np.histogram(data, bins=int(np.sqrt(len(data))))
   half_bins, cdf = cdf_hist(n,bins)

   mu0,c0 = landau_fit(data)[0]
   x00, std0 = np.mean(half_bins), np.std(half_bins)/2

   # Fit with bounds to prevent negative sigma
   bounds = ([mu_l, c_l, min(np.min(half_bins),x0_l), std_l], [mu_u, c_u, max(np.max(half_bins),x0_u), std_u])
   if mu0>mu_u or mu0<mu_l: mu0=(mu_l+mu_u)/2
   if c0>c_u or c0<c_l: c0=(c_l+c_u)/2
   if x00>x0_u or x00<x0_l: x00=(x0_l+x0_u)/2
   if std0>mu_u or std0<std_l: std0=(std_l+std_u)/2

   # Initial guesses: based on prior Landau fit and data estimates
   p0 = [mu0, c0, x00, std0]  # mu, c, mean, std
   lsg = landau_star_gauss_fastest if fast else landau_star_gauss
   popt, pcov = curve_fit(lambda x, mu, c,x0, sigma: lsg(mu, c, x0, sigma,l,u,cdf=True)(x),
                       half_bins, cdf, p0=p0, bounds=bounds)
   
   sigma_popts=np.sqrt(np.diag(pcov))
   return popt,sigma_popts

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

# FIT TESTING
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

def chi_squared(data, fit_cdf, n_params,per_ndof=False):
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

def get_thresh(x,y_cdf,rate=1e-3):
   interp = make_interp_spline(x,y_cdf,5)
   return root_scalar(lambda t:interp(t)-rate,bracket=(min(x),max(x))).root

lib={'Landau':{
    'fit_func':landau_fit,
    'pdf_func':lambda x, params: landau.pdf(x, loc=params[0], scale=params[1])}
}



   #  'Langauss':{
   #  'fit_func':langauss_fit,
   #  'pdf_func':lambda x, params: langauss.pdf(x, landau_x_mpv=params[0], landau_xi=params[2], gauss_sigma=params[4])}
