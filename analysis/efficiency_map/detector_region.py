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
         plt.title(f"Histogram of Timing Differences (Channel {self.ch})")
         plt.xlabel(r"$\Delta t$ (s)")
         plt.ylabel("Probability Density")
         plt.hist(dts,bins=round(np.sqrt(len(dts))),density=True,label="Raw data")
         x = np.linspace(np.min(dts),np.max(dts),1000)
         mu, sigma = self.dt_params
         plt.plot(x,norm.pdf(x, loc=mu, scale=sigma), label=r"$\mu$="+f"{mu}"+r"$\sigma$="+f"{sigma}")
         plt.legend()
         plt.show()
         
      return self.dt_params
