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
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
FACILITIES = {
    'IAG': {
        'portal_url': 'https://observe.monet.uni-goettingen.de',
        'archive_url': 'https://archive.monet.uni-goettingen.de',
        'api_key': '',
    },
    'IAG50Transit': {
        'telescope_class': '0m5',
        'instrument_type': '0M5 SBIG6303E',
        'proposal': 'exo',
    },
}

SITES = {
    'McDonald': {
        'transitObservationConstraints': {
            'maxMagnitude': 20,
            'minTransitDepthInMmag': 1,
        },
        'instrument': '1M2 SBIG8300'
    },
    'Sutherland': {
        'transitObservationConstraints': {
            'maxMagnitude': 20,
            'minTransitDepthInMmag': 1,
        },
        'instrument': '1M2 FLI230'
    },
    'Göttingen': {
        'transitObservationConstraints': {
            'maxMagnitude': 14,
            'minTransitDepthInMmag': 1,
        },
        'instrument': '0M5 SBIG6303E'
    },
}
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
