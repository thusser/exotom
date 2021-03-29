# EXOTOM - TOM for Observing & Analysing Exoplanet Transits

## Project local dev setup
Clone exotom repo
```
git clone https://github.com/thusser/exotom.git
cd exotom
```

### Create & activate virtual environment for python
```
python3 -m venv exotom_env
source exotom_env/bin/activate
```

### Install tom_iag

Clone tom_iag to top-level of project
```
git clone https://github.com/thusser/tom_iag
cd tom_iag
python setup.py install
cd ..
```

### python dependencies
```
pip install -r requirements.txt
```

### local_settings
For local development create `local_settings.py` at top-level of project with following content (fill in your observation portal api key)
```
import os
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
}
FACILITIES = {
    "IAG": {
        "portal_url": "https://observe.monet.uni-goettingen.de",
        "archive_url": "https://archive.monet.uni-goettingen.de",
        "api_key": "<FILL IN YOUR API KEY>",
    },
    "IAG50Transit": {
        "telescope_class": "0m5",
        "instrument_type": "0M5 SBIG6303E",
        "proposal": "exo",
    },
}

SITES = {
    "McDonald": {
        "transitObservationConstraints": {
            "maxMagnitude": 16,
            "minTransitDepthInMmag": 1,
        },
        "instrument": "1M2 SBIG8300",
    },
    "Sutherland": {
        "transitObservationConstraints": {
            "maxMagnitude": 16,
            "minTransitDepthInMmag": 1,
        },
        "instrument": "1M2 FLI230",
    },
    "Göttingen": {
        "transitObservationConstraints": {
            "maxMagnitude": 14,
            "minTransitDepthInMmag": 1,
        },
        "instrument": "0M5 SBIG6303E",
    },
}

COORDS_BY_INSTRUMENT = {
    "1M2 SBIG8300": {
        "latitude": 30.679,
        "longitude": -104.015,
        "elevation": 2027,
    },
    "1M2 FLI230": {
        "latitude": -32.38,
        "longitude": 20.81,
        "elevation": 1804,
    },
    "0M5 SBIG6303E": {
        "latitude": 51.560583,
        "longitude": 9.944333,
        "elevation": 201,
    },
}

# gives 1-dimensional exposure time model exp_time = f(mag)
# see ./notebooks/exposure_times notebook
EXPOSURE_TIME_MODEL_BY_INSTRUMENT = {
    "1M2 SBIG8300": lambda mag: 7.92e-05 * np.exp(9.24e-01 * mag),
    "1M2 FLI230": lambda mag: 6.56e-05 * np.exp(9.22e-01 * mag),
    "0M5 SBIG6303E": lambda mag: 8e-3 * np.exp(6.10e-01 * mag),
}

PROPOSALS = {"priority": "exo", "low_priority": "exofiller"}

```

### make django migrations
```
# python manage.py makemigrations #(to see migrations)
python manage.py migrate
```

### Create admin user
```
python manage.py createsuperuser
```

### Run dev server
```
python manage.py runserver
```

## Git hooks

Install pre-commit hook through python package pre-commit
```
pre-commit install
```
