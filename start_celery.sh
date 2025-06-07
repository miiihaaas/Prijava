#!/bin/bash

# Putanja do Python virtualnog okruženja
VENV_PATH="/home/prijavao/virtualenv/prijava.online/0001/3.12"

# Aktiviranje virtualnog okruženja
source $VENV_PATH/bin/activate

# Putanja do prijava direktorijuma
PRIJAVA_PATH="/home/prijavao/prijava.online/0001"

# Postavljanje environment varijabli
export PYTHONPATH=$PRIJAVA_PATH:$PYTHONPATH

# Pokretanje Celery radnika
cd $PRIJAVA_PATH
celery -A prijava.celery_app.celery worker --loglevel=info
