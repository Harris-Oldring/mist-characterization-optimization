from globalvars import *
import uproot
import numpy as np

class Data:
    def __init__(self,id=None):
        self.db = dict()
        self.NEvents = 0
        self.branches = []
        self.fnames = []
        self.duration = 0
        self.channel = -1
        self.event_rate = 0
        self.Eoverflows = 0
        self.id = id

    def __add__(self,other):
        if type(other)!=type(self):
            raise TypeError()
        # elif self.channel!=other.channel:
        #     raise TypeError(f"These data sets are from different channels ({self.channel} and {other.channel}) and should not be combined.")
        else:
            newdata=Data()
            skeys, okeys = self.db.keys(), other.db.keys()
            # Logic for empty data addition
            if len(skeys) == 0:
                if len(okeys) == 0:
                    return newdata
                mkeys, mdata, nkeys = okeys, other, skeys
            else:
                mkeys, mdata, nkeys = skeys, self, okeys

            for dtype in mkeys:
                if dtype not in nkeys:
                    newdata.db[dtype]=mdata.db[dtype]
                else:
                    newdata.db[dtype]=np.concatenate((self.db[dtype],other.db[dtype]), axis=0)
            sorted_indices = np.argsort(newdata.db['Time'])
            for dtype in newdata.db.keys():
                # Energy has fewer events (overflow was removed)
                if dtype == 'Energy':
                    mask = np.array(sorted_indices) < len(newdata.db['Energy'])
                    newdata.db['Energy']=newdata.db['Energy'][sorted_indices[mask]]
                # elif dtype == 'Height':
                #     mask = np.array(sorted_indices) < len(newdata.db['Height'])
                #     newdata.db['Height']=newdata.db['Height'][sorted_indices[mask]]
                else:
                    newdata.db[dtype]=newdata.db[dtype][sorted_indices]

            newdata.NEvents = self.NEvents + other.NEvents
            newdata.duration = np.max(newdata.db['Time']) - np.min(newdata.db['Time'])
            newdata.event_rate = newdata.compute_event_rate()
            newdata.Eoverflows = self.Eoverflows + other.Eoverflows
            newdata.channel = self.channel if self.channel == other.channel else 'all'
            newdata.id = self.id

            return newdata
        
    def __mod__(self, other):
        if not isinstance(other, (list, np.ndarray)):
            raise TypeError()
        elif len(other) != len(self.db['Time']):
            raise IndexError(f"The length of the mask provided ({len(other)}) does not match the length of the data (({len(self.db['Time'])}))")
        else:
            newdata=Data()
            for dtype in self.db.keys():
                if dtype == 'Energy':
                    newdata.db['Energy']=self.db['Energy'][other[:len(self.db['Energy'])]]
                else:
                    newdata.db[dtype]=self.db[dtype][other]
            sorted_indices = np.argsort(newdata.db['Time'])
            for dtype in newdata.db.keys():
                # Energy has fewer events (overflow was removed)
                if dtype == 'Energy':
                    mask = np.array(sorted_indices) < len(newdata.db['Energy'])
                    newdata.db['Energy']=newdata.db['Energy'][sorted_indices[mask]]
                # elif dtype == 'Height':
                #     mask = np.array(sorted_indices) < len(newdata.db['Height'])
                #     newdata.db['Height']=newdata.db['Height'][sorted_indices[mask]]
                else:
                    newdata.db[dtype]=newdata.db[dtype][sorted_indices]

            t_arr = newdata.db['Time']
            newdata.NEvents = len(t_arr)
            newdata.duration = t_arr[-1] - t_arr[0]
            newdata.Eoverflows = newdata.NEvents - len(newdata.db['Energy'])
            newdata.event_rate = newdata.compute_event_rate()
            newdata.id = self.id

            return newdata
    
    def __str__(self):
        base = [self.channel, self.NEvents, self.duration, self.event_rate, self.Eoverflows]
        return f'  {base[0]:>11} | {base[1]:>20} | {base[2]:>10.0f} s | {base[3]:>13} (events/s) | {base[4]:>20.0f} '

    def load_file(self,fname,n_max=None,mask_overflow=True,lowmem=True):
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
        waves = []
        for wave in tree["Samples"].array(entry_stop=self.NEvents, library="np"):
            b = np.mean(wave[:N_BASELINE])
            m = np.max(wave[N_BASELINE:]) if POS_POLARITY else np.min(wave[N_BASELINE:])
            height += [(m-b)*LSB]
            baseline.append(b*LSB)
            if not lowmem: waves.append(np.array(wave)*LSB - OFFSET)
        
        sorted_indices = np.argsort(time) # Sorts based on time
        self.db['Time']=np.array(time)[sorted_indices]
        self.db['Height']=np.array(height)[sorted_indices]
        self.db['Baseline']=np.array(baseline)[sorted_indices]
        self.db['Energy']=np.array(tree["Energy"].array(entry_stop=self.NEvents, library="np"))[sorted_indices]
        self.db['Channel']=np.array(tree["Channel"].array(entry_stop=self.NEvents, library="np"))[sorted_indices]
        if not lowmem: self.db['Signal']=np.array(waves)[sorted_indices]
        self.duration= time[-1]-time[0]       
        self.channel = self.db['Channel'][0]
        self.event_rate = self.compute_event_rate()
        
        # Remove and record Energy overflow events
        mask = self.get_overflow_mask()
        self.db['Energy'] = self.db['Energy'][mask]
        self.Eoverflows = self.NEvents - len(self.db['Energy'])

        # self.db['Height']=self.db['Height'][self.db['Height'] < 700]

    def compute_event_rate(self):
        '''
        Calculate the average event rate for the provided timestamps.
        Returns a dictionary of metrics for the general analysis flow.
        '''
        times = np.asarray(self.db['Time'])
        if times.size < 2:
            return np.nan
        duration = np.max(times) - np.min(times)
        if duration <= 0:
            return np.nan
        n = float(len(times))
        return f"{n/duration:.2f} ± {float(np.sqrt(n))/duration:.2f}"

    def get_overflow_mask(self, display=False):
        '''
        Identifies overflow events based on the energy data and removes them from the target data, since overflow data turns up as
        energies where the energy is at its maximum representable value (2^N - 1).
        Returns a mask that can be applied to the data to remove overflow events and the number of overflow events identified.
        '''
        max_val = max(self.db['Energy'])
        mask=self.db['Energy']!=max_val if np.log2(max_val+1).is_integer() else np.ones_like(self.db['Energy'], dtype=bool)
        Noverflow=len(mask)-np.sum(mask)

        if display: print(f"{Noverflow} overflow events found. This was {100*Noverflow/len(mask)}% of events.")

        return mask

    def average_generic(self, data_type):
        '''
        Computes the average and standard deviation of a 
        '''
        time_data=self.db['Time']
        target_data=self.db[data_type]

        if time_data is None or target_data is None:
            return {'Baseline Stability': np.nan, 'Baseline Spike Count': np.nan}, None

        time_data = np.asarray(time_data)
        target_data = np.asarray(target_data)
        if time_data.size < 2 or target_data.size < 2 or time_data.size != target_data.size:
            return {'Baseline Stability': np.nan, 'Baseline Spike Count': np.nan}, None

        return f'{np.mean(target_data):.2f} ± {np.std(target_data):.2f}'

