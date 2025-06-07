#!/bin/bash

# Putanja do Python virtualnog okruženja
VENV_PATH="/home/prijavao/virtualenv/prijava.online/0001/3.12"

# Aktiviranje virtualnog okruženja
source $VENV_PATH/bin/activate

# Putanja do glavnog direktorijuma
PRIJAVA_PATH="/home/prijavao/prijava.online/0001"

# Putanja do Python modula
PYTHON_MODULE_PATH="$PRIJAVA_PATH/Prijava"

# Postavljanje environment varijabli
export PYTHONPATH=$PYTHON_MODULE_PATH:$PYTHONPATH

# Pokretanje Celery radnika
cd $PYTHON_MODULE_PATH

# Koristi ispravnu putanju do celery aplikacije
celery -A Prijava.prijava.celery_app worker --loglevel=debug