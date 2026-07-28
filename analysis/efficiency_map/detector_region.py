import numpy as np
import matplotlib.pyplot as plt
from scipy.stats import norm

import sys
from pathlib import Path
sys.path.insert(0, Path.cwd() / 'src')
from fit_analysis import FitResult
from analysis_lib import gauss_fit
import matplotlib.pyplot as plt

class DetectorRegion:
   def __init__(self, id, data, nmt):
      self.id = id
      self.data = data
      self.ch = self.data.db['Channel'][0]
      self.nmt = nmt
      self.NEvents = data.NEvents
      self.duration = data.duration
      self.event_rate = data.NEvents / data.duration
      self.ph_mpv = -1
      self.EMG_params = []
      self.dt_params = []

   def get_ph_mpv(self, plot=False):
      save = not plot
      langauss_fit = FitResult(self.data.db['Height'], 'Langauss', ch=self.ch, save=save)
      self.ph_mpv = langauss_fit.params[0]
      return self.ph_mpv

   def get_EMG_params(self, plot=False):
      save = not plot
      if not save:
         print(f"TEST ID: {self.id}")
      EMG_fit = FitResult(self.data.db['Energy'], 'EMG', ch=self.ch, save=save)
      self.EMG_params = EMG_fit.params
      return EMG_fit.params
   
   def get_dt_params(self, reference, plot=False):
      dts = reference - self.nmt
      self.dt_params,_ = gauss_fit(dts)
      if plot:
         plt.figure(figsize=(3,4))
         # plt.title(f"Histogram of Timing Differences (Channel {self.ch})")
         # plt.title("Sample Histogram of Timing Differences Between Two Scintillators")
         plt.xlabel(r"$\Delta t$ (ns)")
         plt.ylabel("Probability Density")
         plt.hist(dts*1e9,bins=round(np.sqrt(len(dts))),density=True,label="Raw data")
         x = np.linspace(np.min(dts),np.max(dts),1000)*1e9
         mu, sigma = self.dt_params*1e9
         plt.plot(x,norm.pdf(x, loc=mu, scale=sigma),label='Gaussian Fit')
         print(r"$\mu$="+f"{mu:.2f} ns\n"+r"$\sigma$="+f"{sigma:.2f} ns",norm.pdf(x, loc=mu, scale=sigma)[333])
         i_max = np.argmax(norm.pdf(x, loc=mu, scale=sigma))
         ytext = norm.pdf(x, loc=mu, scale=sigma)[i_max]/2
         xtext = x[(1000-i_max)//2] if i_max > 500 else x[i_max//2]
         # plt.text(xtext,ytext,r"$\mu$="+f"{mu:.2f} ns\n"+r"$\sigma$="+f"{sigma:.2f} ns")
         # plt.legend()
         plt.show()
         
      return self.dt_params
