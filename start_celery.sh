#!/bin/bash

# Putanja do Python virtualnog okruženja
VENV_PATH="/home/prijavao/virtualenv/prijava.online/0001/3.12"

# Aktiviranje virtualnog okruženja
source $VENV_PATH/bin/activate

# Putanja do prijava direktorijuma
PRIJAVA_PATH="/home/prijavao/prijava.online/0001"

# Postavljanje environment varijabli
export PYTHONPATH=$PRIJAVA_PATH:$PYTHONPATH

# Dodajemo direktorijum Prijava u PYTHONPATH ako postoji
if [ -d "$PRIJAVA_PATH/Prijava" ]; then
    export PYTHONPATH=$PRIJAVA_PATH/Prijava:$PYTHONPATH
fi

# Pokretanje Celery radnika
cd $PRIJAVA_PATH

# Koristi samo 'prijava' kao modul, a ne prijava.celery_app.celery
celery -A prijava.celery_app worker --loglevel=debug
