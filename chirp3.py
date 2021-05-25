import numpy as np
import matplotlib.pyplot as plt

def _lchirp(N, tmin=0, tmax=1, fmin=0, fmax=None):
    fmax = fmax if fmax is not None else N / 2
    t = np.linspace(tmin, tmax, N, endpoint=True)

    a = (fmin - fmax) / (tmin - tmax)
    b = (fmin*tmax - fmax*tmin) / (tmax - tmin)

    phi = (a/2)*(t**2 - tmin**2) + b*(t - tmin)
    phi *= (2*np.pi)
    return phi

def lchirp(N, tmin=0, tmax=1, fmin=0, fmax=None, zero_phase_tmin=True, cos=True):
    phi = _lchirp(N, tmin, tmax, fmin, fmax)
    if zero_phase_tmin:
        phi *= ( (phi[-1] - phi[-1] % (2*np.pi)) / phi[-1] )
    else:
        phi -= (phi[-1] % (2*np.pi))
    fn = np.cos if cos else np.sin
    return fn(phi)

f0 = 7000
f1 = 17000
samplerate = 192000
T = .004

N = int(samplerate * T)
tmin = 0
tmax = T

t = np.linspace(tmin, tmax, N, endpoint=True)
for zero_phase_min in (True, False):
    for cos in (True, False):
        x = lchirp(N=int(samplerate * T), tmin=tmin, tmax=tmax, fmin=f0, fmax=f1,
                   zero_phase_tmin=zero_phase_min, cos=cos)
        plt.plot(t, x)
        plt.title("cos={}, zero_phase_tmin={}".format(cos, zero_phase_min),
                  weight='bold', fontsize=17, loc='left')
        plt.show()