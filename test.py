import requests
import concurrent.futures
import time
from bs4 import BeautifulSoup
import re

# Funkcija za izdvajanje CSRF tokena iz HTML-a
def extract_csrf_token(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Tražimo input polje sa csrf_token-om
        csrf_input = soup.find('input', {'name': 'csrf_token'})
        if csrf_input:
            return csrf_input.get('value')
        return None
    except Exception as e:
        print(f"Greška pri izdvajanju CSRF tokena: {e}")
        return None

# Funkcija za izdvajanje form_id iz HTML-a
def extract_form_id(html_content):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        # Tražimo input polje sa form_id
        form_id_input = soup.find('input', {'name': 'form_id'})
        if form_id_input:
            return form_id_input.get('value')
        return None
    except Exception as e:
        print(f"Greška pri izdvajanju form_id: {e}")
        return None

def send_request(i):
    # Prva poseta da dobijemo CSRF token i form_id
    s = requests.Session()
    response = s.get('https://prijava.online/0001/application')
    
    # Izvlačenje CSRF tokena i form_id
    csrf_token = extract_csrf_token(response.text)
    form_id = extract_form_id(response.text)
    
    if not csrf_token or not form_id:
        raise Exception(f"Nemoguće izdvojiti CSRF token ili form_id iz odgovora")
    
    data = {
        'csrf_token': csrf_token,
        'form_id': form_id,
        'children_name': f'Test{i}',
        'children_surname': f'Testić{i}',
        'mother_name': f'Majka{i}',
        'mother_surname': f'Majkić{i}',
        'father_name': f'Otac{i}',
        'father_surname': f'Otac{i}',
        'grade': '1',
        'class_number': '1',
        'consent': 'y'  # Odgovara vrednosti checkboxa
    }
    
    # Slanje POST zahteva
    return s.post('https://prijava.online/0001/application', data=data)

# Slanje 50 zahteva istovremeno
with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
    futures = [executor.submit(send_request, i) for i in range(50)]
    
    for future in concurrent.futures.as_completed(futures):
        try:
            result = future.result()
            print(f"Status kod: {result.status_code}")
        except Exception as e:
            print(f"Greška: {e}")