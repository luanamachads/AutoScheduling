import sys
import requests
import yaml
from argparse import ArgumentParser
from datetime import datetime, timedelta
import pytz

BASE_URL = 'https://portal.ufsm.br/mobile/webservice'

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
    response = requests.post(
        f'{BASE_URL}/generateToken',
        json={**config['environment'], 'login': username, 'senha': password}
    )
    data = response.json()
    if data['error']:
        raise ValueError(data['mensagem'])
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
    parser = ArgumentParser(description='Agenda automaticamente as refeições do RU da UFSM.')
    parser.add_argument('-u', '--username', required=True, help='Sua matrícula do aplicativo da UFSM.')
    parser.add_argument('-p', '--password', required=True, help='Sua senha do aplicativo da UFSM.')
    args = parser.parse_args()

    print('Lendo configuração...')
    config = Config('config.yaml')

    now = datetime.now(pytz.timezone('Brazil/East'))
    tomorrow = now + timedelta(1)
    tomorrow_schedules = find_schedules(config, tomorrow)

    if tomorrow_schedules:
        print(f'Encontrado {len(tomorrow_schedules)} refeição(s) para serem agendadas.')
        try:
            access_token = login(config, args.username, args.password)
            for schedule in tomorrow_schedules:
                statuses = schedule_meal(access_token, tomorrow, tomorrow, schedule)
                for status in statuses:
                    date = datetime.strptime(status['dataRefAgendada'], '%Y-%m-%d %H:%M:%S')
                    message = f"{date.strftime('%d/%m/%Y')} - RU {schedule['restaurant']} ({status['tipoRefeicao']}): "
                    print(message + ('Agendado com sucesso.' if status['sucesso'] else f'Erro: {status["impedimento"]}'))
        except Exception as e:
            print(f'Erro ao executar o agendamento: {e}')
            sys.exit(1)
    else:
        print('Não há nenhuma refeição para ser agendada amanhã.')

if __name__ == '__main__':
    main()
