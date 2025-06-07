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
export PYTHONPATH=$PRIJAVA_PATH:$PYTHON_MODULE_PATH:$PYTHONPATH

# Prikazujemo trenutni Python path za debug
echo "PYTHONPATH = $PYTHONPATH"

# Pokretanje Celery radnika
cd $PRIJAVA_PATH

# Koristi ispravnu putanju do celery aplikacije
celery -A prijava.celery_app worker --loglevel=debug