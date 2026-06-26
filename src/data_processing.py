from globalvars import *
import uproot
import numpy as np

class Data:
    def __init__(self):
        self.db=dict()
        self.NEvents=0
        self.branches=[]
        self.fnames=[]
        self.duration=0
        self.channel=-1

    def __add__(self,other):
        if type(other)!=type(self):
            raise TypeError()
        elif self.channel!=other.channel:
            raise TypeError(f"These data sets are from different channels ({self.channel} and {other.channel}) and should not be combined.")
        else:
            newdata=Data()
            for dtype in self.db.keys():
                newdata.db[dtype]=np.append(self.db[dtype],other.db[dtype])
            sorted_indices = np.argsort(newdata.db['time'])
            for dtype in newdata.db.keys():
                newdata.db[dtype]=newdata.db[dtype][sorted_indices]
            return newdata
            


    def load_file(self,fname,n_max=None,mask_overflow=True):
        '''
        Given the name of a root file, return np arrays with relevant data.
        file - the filename of the .root file to be loaded
        FSR  - The full scale range of the digitizer in mV.
        bits - The number of bits in the digitizer.
        n_baseline - The number of samples at the beginning of the waveform to use for baseline calculation.
        polarity - The polarity of the signals, either 'positive' or 'negative'.
        n_max - The maximum number of events processed. 
        '''
        # Load root file
        rootfile = uproot.open(fname)
        if len(rootfile.keys(filter_classname="TTree"))==0:
            print(rootfile.keys())
            print(rootfile.keys(filter_classname="TTree"))
            print(rootfile.classnames())
            raise FileExistsError("root file contains 0 TTrees")
        tree = rootfile[rootfile.keys(filter_classname="TTree")[0]] # Uses the first TTree in the root file
        
        # Extract the relevant branches from the TTree
        n= tree.num_entries
        self.NEvents = min(n_max, n) if n_max else n
        timestamp = tree["Timestamp"].array(entry_stop=self.NEvents, library="np")
        time = timestamp/1e12 # Convert picoseconds to seconds
        height = []
        baseline = []
        for wave in tree["Samples"].array(entry_stop=self.NEvents, library="np"):
            b = np.mean(wave[:N_BASELINE])
            m = np.max(wave[N_BASELINE:]) if POS_POLARITY else np.min(wave[N_BASELINE:])
            height += [(m-b)*LSB]
            baseline.append(b*LSB)
        
        sorted_indices = np.argsort(time) # Sorts based on time
        self.db['Time']=np.array(time)[sorted_indices]
        self.db['Height']=np.array(height)[sorted_indices]
        self.db['Baseline']=np.array(baseline)[sorted_indices]
        self.db['Energy']=np.array(tree["Energy"].array(entry_stop=self.NEvents, library="np"))[sorted_indices]
        self.db['Channel']=np.array(tree["Channel"].array(entry_stop=self.NEvents, library="np"))[sorted_indices]
        self.duration= time[-1]-time[0]       
        self.channel=self.db['Channel'][0]
        if mask_overflow: self.mask_overflow()
    
    def mask_overflow(self,convert=False):
        '''
        Identifies overflow events based on the energy data and removes them from the target data, since overflow data turns up as
        energies where the energy is at its maximum representable value (2^N - 1).
        Returns a mask that can be applied to the data to remove overflow events and the number of overflow events identified.
        '''
        max_val = (max(self.db['energy']) + OFFSET)/LSB if convert else max(self.db['energy'])
        mask=self.db['energy']!=max_val if np.log2(max_val+1).is_integer() else np.ones_like(self.db['energy'], dtype=bool)
        Noverflow=len(mask)-np.sum(mask)

        print(f"{Noverflow} overflow events found. This was {100*Noverflow/len(mask)}% of events.")

        for k in self.db.keys(): self.db[k]=self.db[k][mask].tolist()

    def average_event_rate(self):
        '''
        Calculate the average event rate for the provided timestamps.
        Returns a dictionary of metrics for the general analysis flow.
        '''
        times = np.asarray(self.db['time'])
        if times.size < 2:
            return np.nan
        duration = np.max(times) - np.min(times)
        if duration <= 0:
            return np.nan
        n = float(len(times))
        return f"{n/duration:.2f} ± {float(np.sqrt(n))/duration:.2f}"

    def average_generic(self, data_type):
        '''
        Compute a simple baseline stability metric and count baseline spikes.
        Returns x, y values to plot.
        '''
        time_data=self.db['time']
        target_data=self.db[data_type]

        if time_data is None or target_data is None:
            return {'Baseline Stability': np.nan, 'Baseline Spike Count': np.nan}, None

        time_data = np.asarray(time_data)
        target_data = np.asarray(target_data)
        if time_data.size < 2 or target_data.size < 2 or time_data.size != target_data.size:
            return {'Baseline Stability': np.nan, 'Baseline Spike Count': np.nan}, None

        sort_idx = np.argsort(time_data)
        t = time_data[sort_idx]
        tar_sorted = target_data[sort_idx] #originally "sorted" - BAD - dont use existing system methods for names!!!

        return t, tar_sorted

