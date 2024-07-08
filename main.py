import sys
import requests
import yaml
import pytz
from argparse import ArgumentParser
from datetime import datetime, timedelta
import logging

BASE_URL = 'https://portal.ufsm.br/mobile/webservice'

# Configuração de logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def read_config() -> dict:
    with open('settings.yaml', 'r') as document: 
        return yaml.safe_load(document)

def is_weekday(date: datetime, weekday: str) -> bool:
    return date.strftime('%a') == weekday

def resolve_restaurant_id(restaurant: int) -> int:
    return 41 if restaurant == 2 else restaurant

def login(config, username: str, password: str) -> str:
    logging.info(f"Attempting login for user: {username}")
    response = requests.post(
        f'{BASE_URL}/generateToken',
        json={
            'appName': config['environment']['app'],
            'deviceId': config['environment']['device-id'],
            'deviceInfo': config['environment']['device-info'],
            'messageToken': config['environment']['message-token'],
            'login': username,
            'senha': password
        }
    )

    data = response.json()

    if data['error']:
        logging.error(f"Login error: {data['mensagem']}")
        raise Exception(data['mensagem'])
    
    return data['token']

def schedule_meal(config, token: str, start: datetime, end: datetime, options: dict) -> list:
    payload = {
        'dataInicio': start.strftime('%Y-%m-%d %H:%M:%S'),
        'dataFim': end.strftime('%Y-%m-%d %H:%M:%S'),
        'idRestaurante': resolve_restaurant_id(options['restaurant']),
        'opcaoVegetariana': options['vegetarian'],
        'tiposRefeicoes': []
    }

    for key, (item_id, desc) in [('coffee', (1, 'Café')), ('lunch', (2, 'Almoço')), ('dinner', (3, 'Janta'))]:
        if options.get(key):
            payload['tiposRefeicoes'].append({
                'descricao': desc,
                'error': False,
                'item': item_id,
                'itemId': item_id,
                'selecionado': True
            })

    response = requests.post(
        f'{BASE_URL}/ru/agendaRefeicoes',
        json=payload,
        headers={'X-UFSM-Device-ID': config['environment']['device-id'], 'X-UFSM-Access-Token': token}
    )
    return response.json()

def main():
    parser = ArgumentParser(description='Automatically schedule meals at UFSM.')
    parser.add_argument('-u', '--username', required=True, help='Your UFSM app username.')
    parser.add_argument('-p', '--password', required=True, help='Your UFSM app password.')
    args = parser.parse_args()

    logging.info('Reading configuration...')
    config = read_config()

    now = datetime.now(pytz.timezone('Brazil/East'))
    tomorrow = now + timedelta(days=1)
    tomorrow_schedules = [s for s in config['schedules'] if is_weekday(tomorrow, s['weekday'])]

    if tomorrow_schedules:
        logging.info(f'Found {len(tomorrow_schedules)} meals to be scheduled.')
        try:
            logging.info('Logging in...')
            access_token = login(config, args.username, args.password)
            for schedule in tomorrow_schedules:
                statuses = schedule_meal(config, access_token, tomorrow, tomorrow, schedule)
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
