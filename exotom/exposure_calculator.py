import numpy as np


def calculate_exposure_time(mag: float) -> float:
    """Calculates exposure time in seconds for star of given magnitude.
    So far only for iag50cm @ 2x2 binning
    """

    # values taken from Marcel Kiel's Bachelor's Thesis.
    mag_vs_exposure = np.array(
        [
            [10.25, 5],
            [11.484, 30],
            [11.41, 15],
            [12.262, 17],
            [12.214, 30],
            [13.3, 55],
        ]
    )

    # exponential fit through dat
    a = 0.016
    b = 0.61

    # compare with http://www.astro.physik.uni-goettingen.de/~hessman/MONET/metc_all.html
    a /= 2
    exposure_time = a * np.exp(b * mag)

    return exposure_time
