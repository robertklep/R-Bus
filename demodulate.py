import pandas as pd
import numpy as np
from scipy import signal
import matplotlib.pyplot as plt

# Read the CSV file
df = pd.read_csv('RigolDS1.csv')

# Assuming the data is in a column named 'signal'
sig = df['CH1(V)'].values#[12020000:12030000]

# Generate time array
t = np.arange(len(sig))

# Create sin and cos with a period of 10 samples
f = 0.1
sin_wave = np.sin(2 * np.pi * t * f)
cos_wave = np.cos(2 * np.pi * t * f)

# Demodulate into I and Q components
I = sig * sin_wave
Q = sig * cos_wave

b, a = signal.butter(5, f)
If = signal.lfilter(b, a, I)
Qf = signal.lfilter(b, a, Q)

# Create a new DataFrame with the results
result_df = pd.DataFrame({
    'I': If,
    'Q': Qf,
    #'sin': sin_wave,
    #'sig': sig,
})

# Write the results to a new CSV file
result_df.to_csv('demodulated_output.csv', index=False)

#result_df.plot()
#plt.show()