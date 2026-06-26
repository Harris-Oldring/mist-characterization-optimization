#LOCAL CONFIG
PARENT_DIR=""

#DIGITIZER SETTINGS
FSR=1000 # The full scale range of the digitizer in mV.
BITS=10 # number of bits in the digitizer
OFFSET=148+8 #amount by which the digitizer shifts the baseline of the waveform, to ensure that large voltages can be represented without overflow.
N_BASELINE=80 # number of samples at the beginning of the waveform to use for baseline calculation.
POS_POLARITY=True # polarity of the signals; True if positive
LSB=FSR/(2**BITS-1) # Least Significant Bit in mV (-1 because the range starts at 0 and not ideal transition width) 
