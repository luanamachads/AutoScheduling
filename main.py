import sys
import requests
import yaml
from argparse import ArgumentParser
from datetime import datetime, timedelta
import pytz
import logging

BASE_URL = 'https://portal.ufsm.br/mobile/webservice'

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("agendamento.log"),
                        logging.StreamHandler(sys.stdout)
                    ])

class Config:
    def __init__(self, filepath: str):
        with open(filepath, 'r') as document:
            self.data = yaml.safe_load(document)

    def __getitem__(self, item):
        return self.data[item]

def is_weekday(date: datetime, weekday: str) -> bool:
    return date.strftime('%a') == weekday

def resolve_restaurant_id(restaurant: int) -> int:
    return 41 if restaurant == 2 else restaurant

def login(config: dict, username: str, password: str) -> str:
    logging.info(f"Attempting login for user: {username}")
    response = requests.post(
        f'{BASE_URL}/generateToken',
        json={**config['environment'], 'login': username, 'senha': password}
    )
    data = response.json()
    if data['error']:
        logging.error(f"Login error: {data['mensagem']}")
        raise ValueError(data['mensagem'])
    logging.info("Login successful")
    return data['token']

def schedule_meal(token: str, start: datetime, end: datetime, options: dict) -> list:
    meal_types = {
        'coffee': (1, 'Café'),
        'lunch': (2, 'Almoço'),
        'dinner': (3, 'Janta')
    }
    payload = {
        'dataInicio': start.strftime('%Y-%m-%d %H:%M:%S'),
        'dataFim': end.strftime('%Y-%m-%d %H:%M:%S'),
        'idRestaurante': resolve_restaurant_id(options['restaurant']),
        'opcaoVegetariana': options['vegetarian'],
        'tiposRefeicoes': [
            {'descricao': desc, 'error': False, 'item': item, 'itemId': item, 'selecionado': True}
            for key, (item, desc) in meal_types.items() if options.get(key)
        ]
    }
    headers = {'X-UFSM-Device-ID': config['device-id'], 'X-UFSM-Access-Token': token}
    response = requests.post(f'{BASE_URL}/ru/agendaRefeicoes', json=payload, headers=headers)
    return response.json()

def find_schedules(config: dict, date: datetime) -> list:
    return [s for s in config['schedules'] if is_weekday(date, s['weekday'])]

def main():
    parser = ArgumentParser(description='Automatically schedule meals at UFSM.')
    parser.add_argument('-u', '--username', required=True, help='Your UFSM app username.')
    parser.add_argument('-p', '--password', required=True, help='Your UFSM app password.')
    args = parser.parse_args()

    logging.info('Reading configuration...')
    config = Config('settings.yaml')

    now = datetime.now(pytz.timezone('Brazil/East'))
    tomorrow = now + timedelta(days=1)
    tomorrow_schedules = find_schedules(config, tomorrow)

    if tomorrow_schedules:
        logging.info(f'Found {len(tomorrow_schedules)} meals to be scheduled.')
        try:
            access_token = login(config, args.username, args.password)
            for schedule in tomorrow_schedules:
                statuses = schedule_meal(access_token, tomorrow, tomorrow, schedule)
                for status in statuses:
                    date = datetime.strptime(status['dataRefAgendada'], '%Y-%m-%d %H:%M:%S')
                    message = f"{date.strftime('%d/%m/%Y')} - RU {schedule['restaurant']} ({status['tipoRefeicao']}): "
                    logging.info(message + ('Scheduled successfully.' if status['sucesso'] else f'Error: {status["impedimento"]}'))
        except Exception as e:
            logging.error(f'Error while scheduling: {e}')
            sys.exit(1)
    else:
        logging.info('No meals to be scheduled for tomorrow.')

if __name__ == '__main__':
    main()
